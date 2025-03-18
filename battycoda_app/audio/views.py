"""
Views for audio file processing and visualization in BattyCoda.
"""
import os
import json
import logging
import traceback
from django.http import HttpResponse, JsonResponse, FileResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.conf import settings
from celery.result import AsyncResult

from .utils import appropriate_file, create_error_image, get_audio_bit, overview_hwin, normal_hwin
from .tasks import generate_spectrogram_task, prefetch_spectrograms
from ..utils import convert_path_to_os_specific

# Configure logging
logger = logging.getLogger('battycoda.audio')

@login_required
def handle_spectrogram(request):
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
        Django response with the spectrogram image or task status
    """
    # Log request for debugging
    logger.info(f"Spectrogram request with parameters: {request.GET}")
    
    # Validate required parameters
    required_args = ['wav_path', 'channel', 'call', 'numcalls', 'hash', 'overview']
    for arg in required_args:
        if arg not in request.GET:
            logger.error(f"Missing required argument: {arg}")
            return HttpResponse(create_error_image(f"Missing required argument: {arg}"), content_type='image/png')
    
    # Extract path and args
    path = request.GET.get('wav_path')
    mod_path = convert_path_to_os_specific(path)
    args_dict = {k: v for k, v in request.GET.items()}
    
    # Check for async mode
    async_mode = request.GET.get('async', 'false').lower() == 'true'
    prefetch_mode = request.GET.get('prefetch', 'false').lower() == 'true'
    
    # Log the request details for debugging
    logger.info(f"Spectrogram request received: {path} (async={async_mode}, prefetch={prefetch_mode})")
    logger.debug(f"Original path: {path}, Modified path: {mod_path}")
    
    try:
        # Create unique file paths for caching based on the parameters
        args_for_file = request.GET.copy()
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
                    current_call = int(request.GET['call'])
                    total_calls = int(request.GET['numcalls'])
                    if current_call + 1 < total_calls:
                        # Prefetch next 3 calls or remaining calls, whichever is smaller
                        prefetch_count = min(3, total_calls - current_call - 1)
                        prefetch_range = (current_call + 1, current_call + prefetch_count)
                        
                        # Launch prefetch task in background
                        prefetch_spectrograms.delay(path, args_dict, prefetch_range)
                        logger.info(f"Prefetching calls {prefetch_range[0]} to {prefetch_range[1]}")
                
                return FileResponse(open(check_path, 'rb'), content_type='image/png')
        
        # Create directories if needed
        folder_path = os.path.dirname(file_path)
        os.makedirs(folder_path, exist_ok=True)
        
        # Image doesn't exist, need to generate it
        logger.info(f"Cache miss. Generating image: {file_path}")
        
        # Launch Celery task to generate the image
        # Use the full task name to ensure it's found properly
        from celery import current_app
        task = current_app.send_task(
            'battycoda_app.audio.tasks.generate_spectrogram_task',
            args=[path, args_dict, file_path]
        )
        
        # If async mode, return task ID immediately
        if async_mode:
            return JsonResponse({
                'status': 'queued',
                'task_id': task.id,
                'poll_url': reverse('battycoda_app:task_status', kwargs={'task_id': task.id})
            })
            
        # Otherwise, wait for task to complete with timeout
        try:
            # Wait for task to complete (with timeout)
            result = task.get(timeout=15.0)  # 15 second timeout
            
            if result.get('status') == 'success':
                # Prefetch next call if needed
                if prefetch_mode:
                    current_call = int(request.GET['call'])
                    total_calls = int(request.GET['numcalls'])
                    if current_call + 1 < total_calls:
                        next_args = args_dict.copy()
                        next_args['call'] = str(current_call + 1)
                        from celery import current_app
                        current_app.send_task(
                            'battycoda_app.audio.tasks.generate_spectrogram_task',
                            args=[path, next_args]
                        )
                        logger.info(f"Prefetching next call: {current_call + 1}")
                
                # Check both possible file paths
                for check_path in paths_to_check:
                    if os.path.exists(check_path) and os.path.getsize(check_path) > 0:
                        logger.info(f"Successfully generated image: {check_path}")
                        return FileResponse(open(check_path, 'rb'), content_type='image/png')
                
                # If we get here but task reported success, something went wrong
                error_img_path = create_error_image("Task reported success but image was not found.")
                return FileResponse(open(error_img_path, 'rb'), content_type='image/png')
            else:
                # Task failed
                error_msg = result.get('error', 'Unknown error')
                logger.error(f"Task failed to generate image: {error_msg}")
                error_img_path = create_error_image(f"Failed to generate image: {error_msg}")
                return FileResponse(open(error_img_path, 'rb'), content_type='image/png')
                
        except Exception as e:
            logger.error(f"Error waiting for task: {str(e)}")
            error_img_path = create_error_image(f"Error waiting for task completion: {str(e)}")
            return FileResponse(open(error_img_path, 'rb'), content_type='image/png')
            
    except Exception as e:
        logger.error(f"Error in handle_spectrogram: {str(e)}")
        logger.debug(traceback.format_exc())
        error_img_path = create_error_image(f"Server error: {str(e)}")
        return FileResponse(open(error_img_path, 'rb'), content_type='image/png')

@login_required
def task_status(request, task_id):
    """
    Check the status of a task.
    
    Args:
        request: Django request
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
    
    return JsonResponse(response)

@login_required
def handle_audio_snippet(request):
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
        Django response with the audio snippet
    """
    # Validate required parameters
    required_args = ['wav_path', 'channel', 'call', 'hash', 'overview', 'loudness']
    for arg in required_args:
        if arg not in request.GET:
            logger.error(f"Missing required argument: {arg}")
            return HttpResponse(f"Missing required parameter: {arg}", status=400)
    
    # Extract and convert path
    path = request.GET.get('wav_path')
    mod_path = convert_path_to_os_specific(path)
    
    # Log the request details for debugging
    logger.info(f"Audio snippet request received: {path}")
    logger.debug(f"Original path: {path}, Modified path: {mod_path}")
    logger.debug(f"Arguments: {request.GET}")
    
    try:
        # Create unique file paths for caching based on the parameters
        args_for_file = request.GET.copy()
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
                os.makedirs(folder_path, exist_ok=True)
            
            # Process audio
            call_to_do = int(request.GET['call'])
            overview = request.GET['overview'] == 'True'
            hwin = overview_hwin if overview else normal_hwin
            
            # Get audio data
            audio_path = os.sep.join(mod_path.split('/'))
            thr_x1, fs, hashof = get_audio_bit(audio_path, call_to_do, hwin())
            
            # Validate hash
            if request.GET['hash'] != hashof:
                logger.error(f"Hash mismatch: {request.GET['hash']} != {hashof}")
                return HttpResponse("Hash validation failed", status=400)
            
            # Check for valid audio data
            if thr_x1 is None or len(thr_x1) == 0:
                logger.error("No audio data returned")
                return HttpResponse("Failed to extract audio data", status=500)
            
            # Extract the specific channel and write audio file
            thr_x1 = thr_x1[:, int(request.GET['channel'])]
            import scipy.io.wavfile
            scipy.io.wavfile.write(file_path,
                                 fs // slowdown,
                                 thr_x1.astype('float32').repeat(slowdown) * float(request.GET['loudness']))
            
            logger.info(f"Generated audio snippet: {file_path}")

        return FileResponse(open(file_path, 'rb'), content_type='audio/wav')
        
    except Exception as e:
        logger.error(f"Error in handle_audio_snippet: {str(e)}")
        logger.debug(traceback.format_exc())
        return HttpResponse(str(e), status=500)