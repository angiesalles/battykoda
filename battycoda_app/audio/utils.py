"""
Utility functions for audio processing in BattyCoda.
"""
import os
import logging
import traceback
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

def get_audio_bit(audio_path, call_number, window_size, extra_params=None):
    """
    Get a specific bit of audio containing a bat call.
    Primary method: Use onset/offset from Task model (passed in extra_params)
    Legacy method: Pull call data from paired pickle file (only used during TaskBatch creation)
    
    Args:
        audio_path: Path to the WAV file
        call_number: Which call to extract (only used for legacy pickle method)
        window_size: Size of the window around the call in milliseconds
        extra_params: Dictionary of extra parameters like onset/offset from Task model
        
    Returns:
        tuple: (audio_data, sample_rate, hash_string)
    """
    try:
        import hashlib
        from scipy.io import wavfile
        
        logger.info(f"Getting audio bit for path: {audio_path}, call: {call_number}")
        
        # Check if audio file exists
        if not os.path.exists(audio_path):
            logger.error(f"Audio file not found: {audio_path}")
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
            
        # Calculate file hash based on path (for consistency across containers)
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
        
        # PREFERRED METHOD: Use onset/offset from Task model via extra_params
        if extra_params and 'onset' in extra_params and 'offset' in extra_params:
            try:
                # Use onset/offset provided in parameters
                onset_time = float(extra_params['onset'])
                offset_time = float(extra_params['offset'])
                
                # Convert to samples
                onset = int(onset_time * fs)
                offset = int(offset_time * fs)
                
                logger.info(f"Using task onset/offset: {onset_time}s-{offset_time}s ({onset}-{offset} samples)")
                
                # Validate boundaries and apply reasonable constraints
                if onset < 0:
                    logger.warning(f"Fixing negative onset: {onset} -> 0")
                    onset = 0
                
                if onset >= len(audiodata):
                    logger.warning(f"Onset beyond file length: {onset} >= {len(audiodata)}, setting to 0")
                    onset = 0
                    
                if offset > len(audiodata):
                    logger.warning(f"Offset beyond file length: {offset} > {len(audiodata)}, setting to file end")
                    offset = len(audiodata)
                    
                if offset <= onset:
                    logger.warning(f"Invalid segment (offset <= onset): {offset} <= {onset}, using whole file")
                    onset = 0
                    offset = len(audiodata)
                
                # Extract audio segment with window padding
                start_idx = max(0, onset - (fs * window_size // 1000))
                end_idx = min(offset + (fs * window_size // 1000), len(audiodata))
                
                logger.debug(f"Extracting segment: start_idx={start_idx}, end_idx={end_idx}")
                audio_segment = audiodata[start_idx:end_idx, :]
                
                logger.info(f"Successfully extracted audio segment: shape={audio_segment.shape}")
                return audio_segment, fs, file_hash
                
            except Exception as e:
                logger.error(f"Error using provided onset/offset: {str(e)}")
                # Use full audio as fallback
                logger.warning(f"Using full audio as fallback due to error")
                return audiodata, fs, file_hash
        
        # FALLBACK: If we don't have onset/offset data, use the full audio
        logger.info(f"No onset/offset data available, using full audio file")
        return audiodata, fs, file_hash
        
    except Exception as e:
        logger.error(f"Error in get_audio_bit: {str(e)}")
        logger.debug(traceback.format_exc())
        return None, 0, ""

def create_error_image(error_message, width=800, height=400):
    """
    Create an error image with a message.
    
    Args:
        error_message: Message to display on the image
        width: Width of the image
        height: Height of the image
        
    Returns:
        str: Path to the generated error image file
    """
    # Create a temporary file for the image
    fd, img_path = tempfile.mkstemp(suffix='.png')
    os.close(fd)
    
    # Create figure and axis
    plt.figure(figsize=(width/100, height/100), dpi=100, facecolor='black')
    ax = plt.axes()
    ax.set_facecolor('black')
    
    # Remove axis ticks
    ax.set_xticks([])
    ax.set_yticks([])
    
    # Add error message
    ax.text(0.5, 0.5, error_message, 
            color='white', fontsize=12, ha='center', va='center',
            wrap=True, bbox=dict(boxstyle='round', facecolor='red', alpha=0.7))
    
    # Save the image
    plt.savefig(img_path, facecolor='black', bbox_inches='tight')
    plt.close()
    
    return img_path

def overview_hwin():
    """Returns the half-window size for overview in samples."""
    return 0

def normal_hwin():
    """Returns the half-window size for detailed view in samples."""
    return 500