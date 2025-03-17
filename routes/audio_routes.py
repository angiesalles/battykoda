"""
Routes for audio snippet generation and serving.
"""
import os
import traceback
import logging
from flask import request, send_file
import scipy.io

from AppropriateFile import appropriate_file
import Hwin
import SoftCreateFolders
import GetAudioBit
import utils
from routes.spectrogram_utils import create_error_image

# Configure logging
logger = logging.getLogger('battykoda.audio_routes')


def handle_audio_snippet():
    """
    Handle audio snippet generation and serving for bat calls.
    
    Required URL parameters:
    - wav_path: Path to the WAV file
    - channel: Audio channel to use
    - call: Call number
    - hash: Hash of the audio file for validation
    - overview: Whether to generate overview (True or False)
    - loudness: Volume level
    
    Returns:
        Flask response with the audio snippet
    """
    # Validate required parameters
    required_args = ['wav_path', 'channel', 'call', 'hash', 'overview', 'loudness']
    for arg in required_args:
        if arg not in request.args:
            logger.error(f"Missing required argument: {arg}")
            return f"Missing required parameter: {arg}", 400
    
    # Extract and convert path
    path = request.args.get('wav_path')
    mod_path = utils.convert_path_to_os_specific(path)
    
    # Log the request details for debugging
    logger.info(f"Audio snippet request received: {path}")
    logger.debug(f"Original path: {path}, Modified path: {mod_path}")
    logger.debug(f"Arguments: {request.args}")
    
    try:
        # Create unique file paths for caching based on the parameters
        args_for_file = request.args.copy()
        # Remove wav_path from args to avoid duplicating it in the file name
        file_args = {k: v for k, v in args_for_file.items() if k != 'wav_path'}
        
        # Generate file paths for caching
        file_path = appropriate_file(path, file_args)
        
        # Create directory if needed and generate audio file if it doesn't exist
        slowdown = 5
        if not os.path.exists(file_path):
            # Create directories if needed
            folder_path = appropriate_file(mod_path, file_args, folder_only=True)
            if not os.path.exists(folder_path):
                logger.info(f"Creating cache directory: {folder_path}")
                SoftCreateFolders.soft_create_folders(folder_path)
            
            # Process audio
            call_to_do = int(request.args['call'])
            overview = request.args['overview'] == 'True'
            hwin = Hwin.overview_hwin if overview else Hwin.normal_hwin
            
            # Get audio data
            audio_path = os.sep.join(mod_path.split('/'))
            thr_x1, fs, hashof = GetAudioBit.get_audio_bit(audio_path, call_to_do, hwin)
            
            # Validate hash
            if request.args['hash'] != hashof:
                logger.error(f"Hash mismatch: {request.args['hash']} != {hashof}")
                return "Hash validation failed", 400
            
            # Extract the specific channel and write audio file
            thr_x1 = thr_x1[:, int(request.args['channel'])]
            scipy.io.wavfile.write(file_path,
                                  fs // slowdown,
                                  thr_x1.astype('float32').repeat(slowdown) * float(request.args['loudness']))
            
            logger.info(f"Generated audio snippet: {file_path}")

        return send_file(file_path)
        
    except Exception as e:
        logger.error(f"Error in handle_audio_snippet: {str(e)}")
        logger.debug(traceback.format_exc())
        return str(e), 500