"""
Routes for spectrogram and audio snippet generation and serving.
"""
import os
import traceback
import logging
from flask import request, send_file, url_for
from flask_login import login_required
import queue

from AppropriateFile import appropriate_file
import Workers
import Hwin
import SoftCreateFolders
import GetAudioBit
import utils
import scipy.io
from routes.spectrogram_utils import create_error_image
import routes.spectrogram_utils as utils_module

# Configure logging
logger = logging.getLogger('battykoda.spectrogram_routes')


def handle_spectrogram():
    """
    Handle spectrogram generation and serving for bat calls.
    
    Required URL parameters:
    - wav_path: Path to the WAV file
    - channel: Audio channel to use
    - call: Call number
    - numcalls: Total number of calls
    - hash: Hash of the audio file for validation
    - overview: Whether to generate overview (0 or 1)
    - contrast: Contrast setting
    
    Returns:
        Flask response with the spectrogram image
    """
    # Validate required parameters
    required_args = ['wav_path', 'channel', 'call', 'numcalls', 'hash', 'overview']
    for arg in required_args:
        if arg not in request.args:
            logger.error(f"Missing required argument: {arg}")
            return create_error_image(f"Missing required argument: {arg}")
    
    # Extract and convert path
    path = request.args.get('wav_path')
    mod_path = utils.convert_path_to_os_specific(path)
    
    # Log the request details for debugging
    logger.info(f"Spectrogram request received: {path}")
    logger.debug(f"Original path: {path}, Modified path: {mod_path}")
    logger.debug(f"Arguments: {request.args}")
    
    try:
        # Create unique file paths for caching based on the parameters
        args_for_file = request.args.copy()
        # Remove wav_path from args to avoid duplicating it in the file name
        file_args = {k: v for k, v in args_for_file.items() if k != 'wav_path'}
        
        # Generate file paths for caching
        file_path = appropriate_file(path, file_args)

        # Log paths being checked
        logger.debug(f"Checking main path: {file_path}")

        # Check if either path exists
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            logger.info(f"Cache hit! Using existing image at primary path: {file_path}")
            return send_file(file_path)

        # Ensure directories exist for both paths
        folder_path = appropriate_file(mod_path, file_args, folder_only=True)
        if not os.path.exists(folder_path):
            logger.info(f"Creating cache directory: {folder_path}")
            os.makedirs(folder_path, exist_ok=True)
            
        # Image doesn't exist, need to generate it
        logger.info(f"Cache miss. Need to generate image: {file_path}")
        
        # Set priority based on channel and overview status
        try:
            # Debug logging for global_user_setting
            logger.debug(f"Global user setting: {utils_module.global_user_setting}")
            
            # Default to priority 2 if there's an issue with global_user_setting
            if utils_module.global_user_setting is None:
                logger.error("Global user setting is None! Using default priority.")
                priority_part = 2
            else:
                priority_part = 0 if int(request.args['channel']) == int(utils_module.global_user_setting.get('main', 1))-1 else 2
                
            overview_part = 1 if request.args['overview'] == '1' else 0
            workload = {'path': mod_path, 'args': request.args}
        except Exception as e:
            logger.error(f"Error setting priority: {str(e)}")
            # Use defaults if there's an error
            priority_part = 2
            overview_part = 0
            workload = {'path': mod_path, 'args': request.args}
        
        # Log the workload
        logger.debug(f"Putting into request queue: {mod_path}")
        
        # Add to processing queue
        try:
            if utils_module.global_request_queue is None:
                logger.error("Request queue is None! Queue not initialized correctly.")
                return create_error_image("Internal server error: Queue not initialized correctly.")
                
            # Add to the queue with priority
            utils_module.global_request_queue.put(Workers.PrioItem(priority_part + overview_part, workload))
            
            # Preload next call if needed
            call_to_do = int(request.args['call'])
            if call_to_do + 1 < int(request.args['numcalls']):
                new_args = request.args.copy()
                new_args['call'] = str(call_to_do+1)
                utils_module.global_request_queue.put(Workers.PrioItem(4 + priority_part, {'path': mod_path, 'args': new_args}))
                
            # Wait for image generation to complete
            try:
                logger.debug("Waiting for image generation to complete...")
                utils_module.global_request_queue.join()
                if 'thread' in workload:
                    workload['thread'].join(timeout=10.0)  # Add a timeout to prevent hanging
                else:
                    logger.warning("No thread in workload to join")
                logger.debug("Queue processing completed")
            except Exception as e:
                logger.error(f"Error waiting for image generation: {str(e)}")
        except Exception as queue_error:
            logger.error(f"Error with request queue: {str(queue_error)}")
            return create_error_image(f"Internal server error: {str(queue_error)}")
            
        # Try both paths again after generation
        paths_to_check = [file_path]
        for check_path in paths_to_check:
            if os.path.exists(check_path) and os.path.getsize(check_path) > 0:
                logger.info(f"Successfully generated image: {check_path}")
                return send_file(check_path)
                
        # If we get here, image generation failed
        logger.error(f"Failed to generate image at path: {file_path}")
        
        # Check source audio files
        audio_path = os.sep.join(mod_path.split('/'))
        audio_path_alt = os.sep.join(path.split('/'))
        
        # Check both possible audio paths
        audio_paths = [audio_path, audio_path_alt]
        audio_exists = False
        pickle_exists = False
        
        for check_audio_path in audio_paths:
            if os.path.exists(check_audio_path):
                audio_exists = True
                if os.path.exists(check_audio_path + '.pickle'):
                    pickle_exists = True
                    break
                    
        if not audio_exists:
            return create_error_image(f"Audio file not found. Tried:\n{audio_path}\n{audio_path_alt}")
        if not pickle_exists:
            return create_error_image(f"Metadata file not found. Tried:\n{audio_path}.pickle\n{audio_path_alt}.pickle")
                
        # Try to list the temp directory to help with debugging
        try:
            import tempfile
            temp_dir = os.path.join(tempfile.gettempdir(), "battykoda_temp")
            if os.path.exists(temp_dir):
                temp_contents = os.listdir(temp_dir)
                logger.debug(f"Temp directory {temp_dir} contents: {temp_contents}")
        except Exception as temp_e:
            logger.error(f"Error listing temp directory: {str(temp_e)}")
            
        # General error message
        return create_error_image(f"Failed to generate image. Please check the server logs.")
            
    except Exception as e:
        logger.error(f"Error in handle_spectrogram: {str(e)}")
        logger.debug(traceback.format_exc())
        # Return empty response
        return "", 404


# Audio snippet handling moved to audio_routes.py