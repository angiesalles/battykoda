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

# Create a timer function for performance tracking - with minimal output
def log_performance(start_time, message):
    """Log performance with elapsed time - only for total task time"""
    # Only log total task completions to reduce log volume
    if "TOTAL" in message:
        elapsed = time.time() - start_time
        logger.info(f"PERF: {message} - {elapsed:.3f}s")

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
    start_time = time.time()
    
    # Create minimal task identifier for logging
    call = args.get('call', '?')
    channel = args.get('channel', '?')
    task_id = f"Call {call} Ch {channel}"
    
    try:
        # Skip state updates to reduce logs
        
        # Get file paths
        if output_path is None:
            output_path = appropriate_file(path, args)
            
        # Convert URL path to OS path (if not already converted)
        if path.startswith('home/'):
            os_path = convert_path_to_os_specific(path)
        else:
            os_path = path
            
        # Generate the spectrogram
        success, output_file, error = generate_spectrogram(os_path, args, output_path)
        
        # Only log results for failures
        if not success:
            logger.error(f"{task_id} FAILED: {error}")
        
        if success:
            return {
                'status': 'success',
                'file_path': output_file,
                'original_path': path,
                'args': args
            }
        else:
            return {
                'status': 'error',
                'error': error if error else 'Failed to generate spectrogram',
                'file_path': output_file
            }
            
    except Exception as e:
        # Only log full errors for catastrophic failures
        logger.error(f"{task_id} CATASTROPHIC ERROR: {str(e)}")
        
        # Retry the task if appropriate
        if self.request.retries < self.max_retries:
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
    DISABLED - This function now does nothing to reduce server load
    
    Args:
        path: Path to the audio file
        base_args: Base arguments dict
        call_range: Tuple of (start_call, end_call)
    
    Returns:
        dict: Status indicating the function is disabled
    """
    logger.info("Prefetching is disabled for performance reasons")
    
    # Return a summary indicating prefetch is disabled
    return {
        'status': 'disabled',
        'message': 'Prefetching is disabled for performance reasons'
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
    # Start performance timer
    start_time = time.time()
    
    if output_path is None:
        output_path = appropriate_file(path, args)
    
    # Extract basic parameters for minimal task ID
    call = args.get('call', '0')
    channel = args.get('channel', '0')
    task_id = f"Call {call} Ch {channel}"
    
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
        
        # Get audio data with direct segment loading if possible
        extra_params = None
        if 'onset' in args and 'offset' in args:
            extra_params = {
                'onset': args['onset'],
                'offset': args['offset']
            }
            
        thr_x1, fs, hashof = get_audio_bit(path, call_to_do, hwin, extra_params)
        
        # Validate audio data
        if thr_x1 is None or thr_x1.size == 0:
            return False, output_path, "Audio data is empty"
            
        # Check channel is valid
        if channel >= thr_x1.shape[1]:
            return False, output_path, f"Channel index {channel} is out of bounds"
            
        # Extract channel
        thr_x1 = thr_x1[:, channel]
        
        # OPTIMIZATION: Skip hash validation to reduce overhead
        # This is safe because we're using file paths that are already validated
        
        # OPTIMIZATION: Use more efficient spectrogram parameters 
        # - Use smaller nperseg for faster computation
        # - Use less overlap to reduce computation
        if overview:
            # For overview, use more detail since we're showing more
            nperseg = 2**8  # 256
            noverlap = 200   # ~75% overlap instead of 99%
            nfft = 2**9      # 512 for better frequency resolution
        else:
            # For call detail view, optimize for speed
            nperseg = 2**7   # 128 
            noverlap = 64    # 50% overlap is standard
            nfft = 2**8      # 256
        
        # Generate spectrogram with optimized parameters
        f, t, sxx = scipy.signal.spectrogram(thr_x1, fs, 
                                             nperseg=nperseg, 
                                             noverlap=noverlap, 
                                             nfft=nfft)
        
        # OPTIMIZATION: Save directly to output_path without tempfile
        # Create figure with optimized output
        plt.figure(figsize=(8, 6), facecolor='black', dpi=100)
        ax = plt.axes()
        ax.set_facecolor('indigo')
        
        # Apply contrast
        temocontrast = 10 ** contrast
        plt.pcolormesh(t, f, np.arctan(temocontrast * sxx), shading='auto')
        
        if not overview:
            plt.xlim(0, 0.050)
            
        # Optimize label rendering
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
            
        # Set title based on whether we're using direct timing or call numbers
        if extra_params:
            onset = float(extra_params['onset'])
            offset = float(extra_params['offset'])
            plt.title(f"Time {onset:.2f}s to {offset:.2f}s", color='white')
        else:
            plt.title(f"Call {call_to_do + 1}", color='white')
        
        # OPTIMIZATION: Write directly to output file
        plt.savefig(output_path, dpi=100, bbox_inches='tight', pad_inches=0.1, 
                    facecolor='black')
        plt.close()
        
        # Verify the file was created and log performance
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            log_performance(start_time, f"{task_id}: TOTAL SPECTROGRAM GENERATION")
            return True, output_path, None
        else:
            logger.error(f"ERROR: Output file not created properly: {output_path}")
            return False, output_path, "Failed to create output file"
                
    except Exception as e:
        logger.error(f"Error generating spectrogram: {str(e)}")
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