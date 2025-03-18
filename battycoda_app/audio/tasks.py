"""
Celery tasks for BattyCoda audio and spectrogram processing.
"""
import os
import time
import logging
import traceback
import tempfile
import shutil
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import scipy.signal
from celery import shared_task, group, current_app
from django.conf import settings

from .utils import appropriate_file, get_audio_bit, overview_hwin, normal_hwin, create_error_image
from ..utils import convert_path_to_os_specific

# Configure logging
logger = logging.getLogger('battycoda.tasks')

# Force matplotlib to not use any Xwindows backend
matplotlib.use('Agg')

@shared_task(bind=True, name='battycoda_app.audio.tasks.generate_spectrogram_task', max_retries=3, retry_backoff=True)
def generate_spectrogram_task(self, path, args, output_path=None):
    """
    Task to generate a spectrogram image.
    
    Args:
        path: Path to the audio file
        args: Dict of parameters (call, channel, etc.)
        output_path: Optional explicit output path
    
    Returns:
        dict: Result information
    """
    try:
        # Update task state to processing
        self.update_state(state="PROCESSING", meta={'progress': 10})
        
        # Get file paths
        if output_path is None:
            output_path = appropriate_file(path, args)
            
        # Convert URL path to OS path (if not already converted)
        if path.startswith('home/'):
            os_path = convert_path_to_os_specific(path)
        else:
            os_path = path
            
        # Update progress
        self.update_state(state="PROCESSING", meta={'progress': 30})
        
        # Generate the spectrogram
        success, output_file, error = generate_spectrogram(os_path, args, output_path)
        
        # Update progress
        self.update_state(state="PROCESSING", meta={'progress': 90})
        
        if success:
            logger.info(f"Task {self.request.id}: Successfully generated {output_file}")
            return {
                'status': 'success',
                'file_path': output_file,
                'original_path': path,
                'args': args
            }
        else:
            logger.error(f"Task {self.request.id}: Failed to generate {output_file}: {error}")
            return {
                'status': 'error',
                'error': error if error else 'Failed to generate spectrogram',
                'file_path': output_file
            }
            
    except Exception as e:
        logger.error(f"Task {self.request.id}: Error generating spectrogram: {str(e)}")
        logger.debug(traceback.format_exc())
        
        # Retry the task if appropriate
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying task {self.request.id} ({self.request.retries+1}/{self.max_retries})")
            raise self.retry(exc=e, countdown=2 ** self.request.retries)
            
        return {
            'status': 'error',
            'error': str(e),
            'path': path,
            'args': args
        }

@shared_task(bind=True, name='audio.prefetch_spectrograms')
def prefetch_spectrograms(self, path, base_args, call_range):
    """
    Prefetch multiple spectrograms for a range of calls.
    
    Args:
        path: Path to the audio file
        base_args: Base arguments dict
        call_range: Tuple of (start_call, end_call)
    
    Returns:
        dict: Summary of prefetched items
    """
    start_call, end_call = call_range
    tasks = []
    
    for call in range(start_call, end_call + 1):
        # Create a copy of args with updated call number
        args = base_args.copy()
        args['call'] = str(call)
        
        # Add task to list
        tasks.append(current_app.send_task.s('battycoda_app.audio.tasks.generate_spectrogram_task', args=[path, args]))
    
    # Execute tasks as a group
    job = group(tasks)
    result = job.apply_async()
    
    # Return a summary
    return {
        'status': 'submitted',
        'total_tasks': len(tasks),
        'call_range': call_range,
        'path': path
    }

def generate_spectrogram(path, args, output_path=None):
    """
    Pure function to generate a spectrogram.
    
    Args:
        path: Path to the audio file
        args: Dict of parameters (call, channel, etc.)
        output_path: Optional output path, will be generated if not provided
        
    Returns:
        tuple: (success, output_path, error_message)
    """
    if output_path is None:
        output_path = appropriate_file(path, args)
    
    logger.info(f"Generating spectrogram: {output_path}")
    logger.debug(f"Parameters: {args}")
    
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Parse parameters
        call_to_do = int(args.get('call', 0))
        overview = args.get('overview') == '1' or args.get('overview') == 'True'
        channel = int(args.get('channel', 0))
        contrast = float(args.get('contrast', 4))
        
        # Select window size
        hwin = overview_hwin() if overview else normal_hwin()
        
        # Get audio data
        logger.debug(f"Getting audio data from: {path}")
        thr_x1, fs, hashof = get_audio_bit(path, call_to_do, hwin)
        
        # Validate audio data
        if thr_x1 is None or thr_x1.size == 0:
            logger.error(f"Audio data is empty or None")
            return False, output_path, "Audio data is empty"
            
        # Check channel is valid
        if channel >= thr_x1.shape[1]:
            logger.error(f"Channel index {channel} is out of bounds for array of shape {thr_x1.shape}")
            return False, output_path, f"Channel index {channel} is out of bounds"
            
        # Extract channel
        thr_x1 = thr_x1[:, channel]
        
        # Verify hash matches
        if args.get('hash') != hashof:
            logger.error(f"Hash mismatch: {args.get('hash')} vs {hashof}")
            return False, output_path, "Hash validation failed"
            
        # Generate spectrogram
        f, t, sxx = scipy.signal.spectrogram(thr_x1, fs, nperseg=2 ** 8, noverlap=254, nfft=2 ** 8)
        
        # Create figure
        plt.figure(figsize=(8, 6), facecolor='black')
        ax = plt.axes()
        ax.set_facecolor('indigo')
        temocontrast = 10 ** contrast
        plt.pcolormesh(t, f, np.arctan(temocontrast * sxx), shading='auto')
        
        if not overview:
            plt.xlim(0, 0.050)
            
        ax.tick_params(axis='x', colors='white')
        ax.tick_params(axis='y', colors='white')
        ax.xaxis.label.set_color('white')
        ax.yaxis.label.set_color('white')
        
        if fs < 0:  # Mark error condition
            plt.ylabel('kevinerror')
            plt.xlabel('kevinerror')
        else:
            plt.ylabel('Frequency [Hz]')
            plt.xlabel('Time [sec]')
        
        # Save to a temporary file first, then move it to final destination
        # This helps avoid partial writes
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        temp_file.close()
        
        logger.debug(f"Saving figure to temp file: {temp_file.name}")
        plt.savefig(temp_file.name, dpi=100)
        plt.close()
        
        # Check if temp file was created successfully
        if os.path.exists(temp_file.name) and os.path.getsize(temp_file.name) > 0:
            # Move the file to the final destination
            logger.debug(f"Moving temp file to: {output_path}")
            shutil.move(temp_file.name, output_path)
            
            # Double-check the file exists and has content
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logger.info(f"Successfully created: {output_path}")
                return True, output_path, None
            else:
                logger.error(f"ERROR: Final file not created properly: {output_path}")
                return False, output_path, "Failed to create output file"
        else:
            logger.error(f"ERROR: Temp file not created properly: {temp_file.name}")
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
            return False, output_path, "Failed to create temporary file"
                
    except Exception as e:
        logger.error(f"Error generating spectrogram: {str(e)}")
        logger.debug(traceback.format_exc())
        try:
            plt.close()  # Make sure to close the figure even on error
        except:
            pass
        
        # Try to create an error image
        try:
            create_error_image(str(e), output_path)
            return False, output_path, str(e)
        except:
            return False, output_path, str(e)