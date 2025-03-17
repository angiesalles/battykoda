"""
Routes for spectrogram and audio snippet generation and serving.
Uses Celery for asynchronous processing.
"""
import os
import time
import traceback
import logging
import tempfile
from flask import request, send_file, url_for, jsonify
from flask_login import login_required
from celery.result import AsyncResult

from AppropriateFile import appropriate_file
import Workers
import Hwin
import SoftCreateFolders
import GetAudioBit
import utils
import scipy.io
from routes.spectrogram_utils import create_error_image
import routes.spectrogram_utils as utils_module
from tasks import generate_spectrogram_task, prefetch_spectrograms

# Configure logging
logger = logging.getLogger('battykoda.spectrogram_routes')


def handle_spectrogram():
    """
    Handle spectrogram generation and serving for bat calls using Celery.
    
    Required URL parameters:
    - wav_path: Path to the WAV file
    - channel: Audio channel to use
    - call: Call number
    - numcalls: Total number of calls
    - hash: Hash of the audio file for validation
    - overview: Whether to generate overview (0 or 1)
    - contrast: Contrast setting
    
    Optional parameters:
    - async: If 'true', returns a task ID instead of waiting for the image
    - prefetch: If 'true', prefetches the next few images in the sequence
    
    Returns:
        Flask response with the spectrogram image or task status
    """
    # Validate required parameters
    required_args = ['wav_path', 'channel', 'call', 'numcalls', 'hash', 'overview']
    for arg in required_args:
        if arg not in request.args:
            logger.error(f"Missing required argument: {arg}")
            return create_error_image(f"Missing required argument: {arg}")
    
    # Extract path and args
    path = request.args.get('wav_path')
    mod_path = utils.convert_path_to_os_specific(path)
    args_dict = request.args.to_dict()
    
    # Check for async mode
    async_mode = request.args.get('async', 'false').lower() == 'true'
    prefetch_mode = request.args.get('prefetch', 'false').lower() == 'true'
    
    # Log the request details for debugging
    logger.info(f"Spectrogram request received: {path} (async={async_mode}, prefetch={prefetch_mode})")
    logger.debug(f"Original path: {path}, Modified path: {mod_path}")
    
    try:
        # Create unique file paths for caching based on the parameters
        args_for_file = request.args.copy()
        file_args = {k: v for k, v in args_for_file.items() if k != 'wav_path'}
        
        # Generate file paths
        file_path = appropriate_file(path, file_args)
        alt_file_path = appropriate_file(mod_path, file_args)
        
        # Check if image already exists
        paths_to_check = [file_path, alt_file_path]
        for check_path in paths_to_check:
            if os.path.exists(check_path) and os.path.getsize(check_path) > 0:
                logger.info(f"Cache hit! Using existing image: {check_path}")
                
                # If prefetch is enabled, launch background task for next calls
                if prefetch_mode:
                    current_call = int(request.args['call'])
                    total_calls = int(request.args['numcalls'])
                    if current_call + 1 < total_calls:
                        # Prefetch next 3 calls or remaining calls, whichever is smaller
                        prefetch_count = min(3, total_calls - current_call - 1)
                        prefetch_range = (current_call + 1, current_call + prefetch_count)
                        
                        # Launch prefetch task in background
                        prefetch_spectrograms.delay(path, args_dict, prefetch_range)
                        logger.info(f"Prefetching calls {prefetch_range[0]} to {prefetch_range[1]}")
                
                return send_file(check_path)
        
        # Create directories if needed
        folder_path = os.path.dirname(file_path)
        os.makedirs(folder_path, exist_ok=True)
        
        # Image doesn't exist, need to generate it
        logger.info(f"Cache miss. Generating image: {file_path}")
        
        # Launch Celery task to generate the image
        task = generate_spectrogram_task.delay(path, args_dict, file_path)
        
        # If async mode, return task ID immediately
        if async_mode:
            return jsonify({
                'status': 'queued',
                'task_id': task.id,
                'poll_url': url_for('task_status', task_id=task.id)
            })
            
        # Otherwise, wait for task to complete with timeout
        try:
            # Wait for task to complete (with timeout)
            result = task.get(timeout=15.0)  # 15 second timeout
            
            if result.get('status') == 'success':
                # Prefetch next call if needed
                if prefetch_mode:
                    current_call = int(request.args['call'])
                    total_calls = int(request.args['numcalls'])
                    if current_call + 1 < total_calls:
                        next_args = args_dict.copy()
                        next_args['call'] = str(current_call + 1)
                        generate_spectrogram_task.delay(path, next_args)
                        logger.info(f"Prefetching next call: {current_call + 1}")
                
                # Check both possible file paths
                for check_path in paths_to_check:
                    if os.path.exists(check_path) and os.path.getsize(check_path) > 0:
                        logger.info(f"Successfully generated image: {check_path}")
                        return send_file(check_path)
                
                # If we get here but task reported success, something went wrong
                return create_error_image("Task reported success but image was not found.")
            else:
                # Task failed
                error_msg = result.get('error', 'Unknown error')
                logger.error(f"Task failed to generate image: {error_msg}")
                return create_error_image(f"Failed to generate image: {error_msg}")
                
        except Exception as e:
            logger.error(f"Error waiting for task: {str(e)}")
            return create_error_image(f"Error waiting for task completion: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error in handle_spectrogram: {str(e)}")
        logger.debug(traceback.format_exc())
        return create_error_image(f"Server error: {str(e)}")


def task_status(task_id):
    """
    Check the status of a task.
    
    Args:
        task_id: ID of the Celery task
        
    Returns:
        JSON response with task status
    """
    task_result = AsyncResult(task_id)
    
    if task_result.state == 'PENDING':
        response = {
            'status': 'pending',
            'message': 'Task is pending'
        }
    elif task_result.state == 'FAILURE':
        response = {
            'status': 'error',
            'message': str(task_result.info)
        }
    elif task_result.state == 'PROCESSING':
        response = {
            'status': 'processing',
            'progress': task_result.info.get('progress', 0),
            'message': 'Task is processing'
        }
    elif task_result.state == 'SUCCESS':
        if task_result.info and 'status' in task_result.info:
            if task_result.info['status'] == 'success':
                response = {
                    'status': 'success',
                    'file_path': task_result.info.get('file_path'),
                    'message': 'Task completed successfully'
                }
            else:
                response = {
                    'status': 'error',
                    'message': task_result.info.get('error', 'Unknown error')
                }
        else:
            response = {
                'status': 'success',
                'message': 'Task completed, but no details available'
            }
    else:
        response = {
            'status': 'unknown',
            'message': f'Unknown task state: {task_result.state}'
        }
    
    return jsonify(response)


# Audio snippet handling moved to audio_routes.py