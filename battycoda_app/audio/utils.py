"""
Utility functions for audio processing in BattyCoda.
"""
import os
import logging
import tempfile
import shutil
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import scipy.signal
import scipy.io
from django.conf import settings

# Configure logging
logger = logging.getLogger('battycoda.audio')

# Force matplotlib to not use any Xwindows backend
matplotlib.use('Agg')

def appropriate_file(path, args, folder_only=False):
    """
    Generate an appropriate file path for storing processed audio or images.
    This is a cache path generation function to keep processed files organized.
    
    Args:
        path: Path to the original audio file
        args: Dict of arguments that affect the processing
        folder_only: If True, return only the folder path, not the file path
        
    Returns:
        str: Path where the processed file should be stored
    """
    # Clean path for cache file
    # Replace '/' with '_' to avoid nested directories beyond a certain point
    if '/' in path:
        parts = path.split('/')
        # Use the last two parts for directory structure to keep it simpler
        dir_path = '_'.join(parts[-2:]) if len(parts) > 1 else parts[0]
    else:
        dir_path = path
    
    # Create a safe directory name (remove problematic characters)
    safe_dir = ''.join(c if c.isalnum() or c in '_-.' else '_' for c in dir_path)
        
    # Create a unique filename based on args
    args_string = '_'.join([f"{k}={v}" for k, v in sorted(args.items()) if k != 'hash'])
    
    # Set up the cache directory in the media folder
    cache_dir = os.path.join(settings.MEDIA_ROOT, 'audio_cache', safe_dir)
    os.makedirs(cache_dir, exist_ok=True)
    
    if folder_only:
        return cache_dir
        
    # Add file extension based on args
    if args.get('overview') in ['1', 'True', True]:
        ext = '.overview.png' if 'contrast' in args else '.overview.wav'
    else:
        ext = '.normal.png' if 'contrast' in args else '.normal.wav'
        
    # Add detail flag if present
    if args.get('detail') == '1':
        ext = '.detail.png'
    
    # Combine into final path
    filename = f"{args_string}{ext}"
    
    # Log the cache path for debugging
    logging.debug(f"Cache path for {path}: {os.path.join(cache_dir, filename)}")
    
    return os.path.join(cache_dir, filename)

def get_audio_bit(audio_path, call_number, window_size):
    """
    Get a specific bit of audio containing a bat call.
    This pulls call data from the paired pickle file and extracts the audio.
    
    Args:
        audio_path: Path to the WAV file
        call_number: Which call to extract
        window_size: Size of the window around the call in milliseconds
        
    Returns:
        tuple: (audio_data, sample_rate, hash_string)
    """
    try:
        import pickle
        import hashlib
        from scipy.io import wavfile
        
        logger.info(f"Getting audio bit for path: {audio_path}, call: {call_number}")
        
        # Check if audio file exists
        if not os.path.exists(audio_path):
            logger.error(f"Audio file not found: {audio_path}")
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
            
        # Check if pickle file exists
        pickle_path = audio_path + '.pickle'
        if not os.path.exists(pickle_path):
            logger.error(f"Pickle file not found: {pickle_path}")
            raise FileNotFoundError(f"Pickle file not found: {pickle_path}")
        
        # Read audio data
        logger.debug(f"Reading audio data")
        
        # Calculate file hash based on path (for consistency across containers)
        # This matches how the hash is generated in wav_file_view
        file_hash = hashlib.md5(audio_path.encode()).hexdigest()
        
        # Read WAV file
        logger.debug(f"Reading WAV file: {audio_path}")
        fs, audiodata = wavfile.read(audio_path)
        
        # Validate audio data
        if audiodata is None or audiodata.size == 0:
            logger.error(f"No audio data found in file: {audio_path}")
            raise ValueError(f"No audio data found in file: {audio_path}")
        
        # Handle mono files by converting to stereo
        if len(audiodata.shape) == 1:
            logger.debug(f"Converting mono audio to stereo (shape before: {audiodata.shape})")
            audiodata = audiodata.reshape([-1, 1]).repeat(2, axis=1)
            logger.debug(f"New shape: {audiodata.shape}")
        
        # Normalize audio data
        audiodata = audiodata.astype(float)
        std = np.std(audiodata)
        if std > 0:
            audiodata /= std
        else:
            logger.warning(f"Audio data has zero standard deviation (silent file): {audio_path}")
        
        # Load segment data from pickle file
        logger.debug(f"Loading segment data from {pickle_path}")
        try:
            with open(pickle_path, 'rb') as pfile:
                segment_data = pickle.load(pfile)
        except Exception as e:
            logger.error(f"Error loading pickle file {pickle_path}: {str(e)}")
            raise
        
        # Validate segment data
        if 'onsets' not in segment_data or 'offsets' not in segment_data:
            logger.error(f"Invalid segment data: missing onsets or offsets")
            raise ValueError(f"Invalid segment data: missing onsets or offsets")
            
        # Validate call index
        if call_number >= len(segment_data['onsets']) or call_number >= len(segment_data['offsets']):
            logger.error(f"Invalid call index {call_number}: out of range (max: {len(segment_data['onsets'])-1})")
            raise IndexError(f"Invalid call index {call_number}: out of range")
        
        # Calculate onset and offset in samples
        onset = int(segment_data['onsets'][call_number] * fs)
        offset = int(segment_data['offsets'][call_number] * fs)
        
        logger.debug(f"Call {call_number}: onset={onset}, offset={offset}, fs={fs}")
        
        # Validate audio data boundaries
        if onset >= len(audiodata) or offset > len(audiodata):
            logger.error(f"Invalid segment boundaries: onset={onset}, offset={offset}, audio length={len(audiodata)}")
            raise ValueError(f"Invalid segment boundaries: onset={onset}, offset={offset}, audio length={len(audiodata)}")
            
        # Extract audio segment with window padding
        start_idx = max(0, onset - (fs * window_size // 1000))
        end_idx = min(offset + (fs * window_size // 1000), len(audiodata))
        
        logger.debug(f"Extracting segment: start_idx={start_idx}, end_idx={end_idx}")
        audio_segment = audiodata[start_idx:end_idx, :]
        
        # Mark segments that are too long or have invalid boundaries
        if (offset-onset)*1.0/fs > 1.0 or offset <= onset:
            logger.warning(f"Marking segment as error due to invalid duration or boundaries")
            fs = -fs
            
        logger.info(f"Successfully extracted audio segment: shape={audio_segment.shape}")
        return audio_segment, fs, file_hash
        
    except Exception as e:
        logger.error(f"Error in get_audio_bit: {str(e)}")
        import traceback
        logger.debug(traceback.format_exc())
        return None, -1, ''

def overview_hwin():
    """Return window size for overview."""
    return 50  # This matches the original Hwin.py value

def normal_hwin():
    """Return window size for normal view."""
    return 10  # This matches the original Hwin.py value

def create_error_image(error_message, output_path=None):
    """
    Create an error image with the given message.
    
    Args:
        error_message: Error message to display
        output_path: Where to save the image (if None, a temp file is created)
        
    Returns:
        str: Path to the error image
    """
    try:
        # Create a temp file if no output path provided
        if output_path is None:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            temp_file.close()
            output_path = temp_file.name
        else:
            # Make sure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Create figure
        fig = plt.figure(figsize=(8, 6), facecolor='red')
        ax = plt.axes()
        
        # Add error message and detailed diagnostics
        ax.text(0.5, 0.7, f"Error: {error_message}", 
                horizontalalignment='center',
                verticalalignment='center',
                transform=ax.transAxes,
                color='white',
                fontsize=14)
                
        # Add some debug info
        import datetime
        debug_info = (
            f"Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Media root: {settings.MEDIA_ROOT}\n"
            f"Error ID: {id(error_message)}"
        )
        
        ax.text(0.5, 0.3, debug_info, 
                horizontalalignment='center',
                verticalalignment='center',
                transform=ax.transAxes,
                color='yellow',
                fontsize=10)
                
        ax.set_axis_off()
        
        # Save image
        plt.savefig(output_path)
        plt.close()
        
        logger.info(f"Created error image at {output_path}: {error_message}")
        return output_path
        
    except Exception as e:
        logger.error(f"Failed to create error image: {str(e)}")
        try:
            plt.close()
        except:
            pass
        return None