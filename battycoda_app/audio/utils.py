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
        import soundfile as sf
        
        # Calculate file hash based on path (for consistency across containers)
        file_hash = hashlib.md5(audio_path.encode()).hexdigest()
        
        # Check if audio file exists
        if not os.path.exists(audio_path):
            logger.error(f"Audio file not found: {audio_path}")
            # Try a few alternate paths
            alt_paths = [
                audio_path.replace('/app/media', ''),
                '/app/media' + audio_path if not audio_path.startswith('/app/media') else audio_path,
                audio_path.replace('/app/media/task_batches', '/task_batches'),
                '/task_batches/' + os.path.basename(audio_path)
            ]
            
            for alt_path in alt_paths:
                if os.path.exists(alt_path):
                    logger.info(f"Found alternate path: {alt_path}")
                    audio_path = alt_path
                    break
            else:
                # No alternate paths found
                raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        # Log file info
        logger.info(f"Processing audio file: {audio_path}")
            
        # OPTIMIZATION: If we have onset/offset data, we can read only the segment we need
        # This avoids loading the entire file for large audio files
        if extra_params and 'onset' in extra_params and 'offset' in extra_params:
            try:
                # Get file info without reading all data
                info = sf.info(audio_path)
                fs = info.samplerate
                
                # Use onset/offset provided in parameters
                onset_time = float(extra_params['onset'])
                offset_time = float(extra_params['offset'])
                
                # Log onset and offset
                logger.info(f"Using task onset/offset: {onset_time:.5f}s-{offset_time:.5f}s ({int(onset_time*fs)}-{int(offset_time*fs)} samples)")
                
                # Add window padding (in seconds)
                window_padding = window_size / 1000  # convert ms to seconds
                start_time = max(0, onset_time - window_padding)
                end_time = min(info.duration, offset_time + window_padding)
                
                # Calculate frames to read
                start_frame = int(start_time * fs)
                num_frames = int((end_time - start_time) * fs)
                
                logger.debug(f"Reading segment from {start_time:.3f}s to {end_time:.3f}s")
                logger.debug(f"Extracting segment: start_idx={start_frame}, end_idx={start_frame+num_frames}")
                
                # Read only the segment we need
                with sf.SoundFile(audio_path) as f:
                    f.seek(start_frame)
                    audio_segment = f.read(num_frames, dtype='float32')
                
                # Handle mono files by converting to stereo
                if len(audio_segment.shape) == 1:
                    audio_segment = audio_segment.reshape([-1, 1])
                    # Add second channel if missing
                    if audio_segment.shape[1] == 1:
                        audio_segment = np.column_stack((audio_segment, audio_segment))
                
                # Normalize audio data (only the segment)
                std = np.std(audio_segment)
                if std > 0:
                    audio_segment /= std
                
                # Ensure output is valid
                if np.isnan(audio_segment).any() or np.isinf(audio_segment).any():
                    logger.warning("Audio segment contains NaN or Inf values, replacing with zeros")
                    audio_segment = np.nan_to_num(audio_segment)
                
                logger.info(f"Successfully extracted audio segment: shape={audio_segment.shape}")
                return audio_segment, fs, file_hash
                
            except Exception as e:
                logger.error(f"Error reading segment, falling back to full file: {str(e)}")
                logger.debug(traceback.format_exc())
                # Fall through to standard method if optimized reading fails
        
        # Standard method - read the entire file
        logger.debug(f"Reading full WAV file: {audio_path}")
        try:
            # First try with soundfile for better robustness
            with sf.SoundFile(audio_path) as f:
                fs = f.samplerate
                audiodata = f.read(dtype='float32')
        except Exception as sf_error:
            logger.warning(f"Error with soundfile, trying wavfile: {str(sf_error)}")
            try:
                fs, audiodata = wavfile.read(audio_path)
            except Exception as wav_error:
                logger.error(f"Failed to read audio file with both libraries: {str(wav_error)}")
                raise
        
        # Validate audio data
        if audiodata is None or audiodata.size == 0:
            logger.error(f"No audio data found in file: {audio_path}")
            raise ValueError(f"No audio data found in file: {audio_path}")
        
        # Convert to float if not already
        if audiodata.dtype != np.float32 and audiodata.dtype != np.float64:
            audiodata = audiodata.astype(np.float32) / np.iinfo(audiodata.dtype).max
        
        # Handle mono files by converting to stereo
        if len(audiodata.shape) == 1:
            audiodata = audiodata.reshape([-1, 1])
            # Add second channel if missing
            if audiodata.shape[1] == 1:
                audiodata = np.column_stack((audiodata, audiodata))
        
        # Normalize audio data
        std = np.std(audiodata)
        if std > 0:
            audiodata /= std
        
        # Ensure output is valid
        if np.isnan(audiodata).any() or np.isinf(audiodata).any():
            logger.warning("Audio data contains NaN or Inf values, replacing with zeros")
            audiodata = np.nan_to_num(audiodata)
        
        # If we have onset/offset, extract just that segment
        if extra_params and 'onset' in extra_params and 'offset' in extra_params:
            onset_time = float(extra_params['onset'])
            offset_time = float(extra_params['offset'])
            
            # Log onset and offset
            logger.info(f"Using task onset/offset: {onset_time:.5f}s-{offset_time:.5f}s ({int(onset_time*fs)}-{int(offset_time*fs)} samples)")
            
            # Convert to samples
            onset = int(onset_time * fs)
            offset = int(offset_time * fs)
            
            # Validate boundaries
            onset = max(0, min(onset, len(audiodata)-1))
            offset = max(onset+1, min(offset, len(audiodata)))
            
            # Extract audio segment with window padding
            start_idx = max(0, onset - (fs * window_size // 1000))
            end_idx = min(offset + (fs * window_size // 1000), len(audiodata))
            
            logger.debug(f"Extracting segment: start_idx={start_idx}, end_idx={end_idx}")
            audio_segment = audiodata[start_idx:end_idx, :]
            logger.info(f"Successfully extracted audio segment: shape={audio_segment.shape}")
            return audio_segment, fs, file_hash
        
        # Return full audio if no segment specified
        logger.info(f"Returning full audio: shape={audiodata.shape}")
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