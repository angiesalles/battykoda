"""
Utility functions for audio processing in BattyCoda.
"""
import logging
import os
import pickle
import tempfile
import traceback

from django.conf import settings

import numpy as np
import scipy.io
import scipy.signal
from PIL import Image

# Configure logging
logger = logging.getLogger("battycoda.audio")


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
    if "/" in path:
        parts = path.split("/")
        # Use the last two parts for directory structure to keep it simpler
        dir_path = "_".join(parts[-2:]) if len(parts) > 1 else parts[0]
    else:
        dir_path = path

    # Create a safe directory name (remove problematic characters)
    safe_dir = "".join(c if c.isalnum() or c in "_-." else "_" for c in dir_path)

    # Create a unique filename based on args
    args_string = "_".join([f"{k}={v}" for k, v in sorted(args.items()) if k != "hash"])

    # Set up the cache directory in the media folder
    cache_dir = os.path.join(settings.MEDIA_ROOT, "audio_cache", safe_dir)
    os.makedirs(cache_dir, exist_ok=True)

    if folder_only:
        return cache_dir

    # Add file extension based on args
    if args.get("overview") in ["1", "True", True]:
        ext = ".overview.png" if "contrast" in args else ".overview.wav"
    else:
        ext = ".normal.png" if "contrast" in args else ".normal.wav"

    # Add detail flag if present
    if args.get("detail") == "1":
        ext = ".detail.png"

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
        window_size: Size of the window around the call in samples (when passed from normal_hwin/overview_hwin)
                     or in milliseconds (when passed directly as a number)
        extra_params: Dictionary of extra parameters like onset/offset from Task model

    Returns:
        tuple: (audio_data, sample_rate, hash_string)
    """
    try:
        import hashlib

        import soundfile as sf
        from scipy.io import wavfile

        # Calculate file hash based on path (for consistency across containers)
        file_hash = hashlib.md5(audio_path.encode()).hexdigest()

        # Check if audio file exists
        if not os.path.exists(audio_path):
            logger.error(f"Audio file not found: {audio_path}")
            # Try a few alternate paths
            alt_paths = [
                audio_path.replace("/app/media", ""),
                "/app/media" + audio_path if not audio_path.startswith("/app/media") else audio_path,
                audio_path.replace("/app/media/task_batches", "/task_batches"),
                "/task_batches/" + os.path.basename(audio_path),
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
        if extra_params and "onset" in extra_params and "offset" in extra_params:
            try:
                # Get file info without reading all data
                info = sf.info(audio_path)
                fs = info.samplerate

                # Use onset/offset provided in parameters
                onset_time = float(extra_params["onset"])
                offset_time = float(extra_params["offset"])

                # Log onset and offset
                logger.info(
                    f"Using task onset/offset: {onset_time:.5f}s-{offset_time:.5f}s ({int(onset_time*fs)}-{int(offset_time*fs)} samples)"
                )

                # Handle window padding (in seconds)
                pre_padding = window_size[0] / 1000  # convert ms to seconds
                post_padding = window_size[1] / 1000
                start_time = max(0, onset_time - pre_padding)
                end_time = min(info.duration, offset_time + post_padding)

                # Calculate frames to read
                start_frame = int(start_time * fs)
                num_frames = int((end_time - start_time) * fs)

                logger.debug(f"Reading segment from {start_time:.3f}s to {end_time:.3f}s")
                logger.debug(f"Extracting segment: start_idx={start_frame}, end_idx={start_frame+num_frames}")

                # Read only the segment we need
                with sf.SoundFile(audio_path) as f:
                    f.seek(start_frame)
                    audio_segment = f.read(num_frames, dtype="float32")

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
                audiodata = f.read(dtype="float32")
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
        if extra_params and "onset" in extra_params and "offset" in extra_params:
            onset_time = float(extra_params["onset"])
            offset_time = float(extra_params["offset"])

            # Log onset and offset
            logger.info(
                f"Using task onset/offset: {onset_time:.5f}s-{offset_time:.5f}s ({int(onset_time*fs)}-{int(offset_time*fs)} samples)"
            )

            # Convert to samples
            onset = int(onset_time * fs)
            offset = int(offset_time * fs)

            # Validate boundaries
            onset = max(0, min(onset, len(audiodata) - 1))
            offset = max(onset + 1, min(offset, len(audiodata)))

            # Extract audio segment with window padding
            pre_padding = window_size[0] / 1000
            post_padding = window_size[1] / 1000
            start_idx = max(0, onset - int(fs * pre_padding))
            end_idx = min(offset + int(fs * post_padding), len(audiodata))

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


def overview_hwin():
    """Returns the window padding as (pre_window, post_window) in milliseconds."""
    return (150, 350)


def normal_hwin():
    """Returns the window padding as (pre_window, post_window) in milliseconds."""
    return (8, 8)


def get_spectrogram_ticks(task, sample_rate=None, normal_window_size=None, overview_window_size=None):
    """Generate tick mark data for spectrograms.
    
    Args:
        task: Task model instance containing onset and offset
        sample_rate: Sample rate of the recording in Hz (optional)
        normal_window_size: Tuple of (pre_window, post_window) in milliseconds for detail view
        overview_window_size: Tuple of (pre_window, post_window) in milliseconds for overview
        
    Returns:
        dict: Dictionary containing x and y tick data for both detail and overview views
    """
    # Use default window sizes if not provided
    if normal_window_size is None:
        normal_window_size = normal_hwin()
    if overview_window_size is None:
        overview_window_size = overview_hwin()
    
    # Calculate call duration in milliseconds
    call_duration_ms = (task.offset - task.onset) * 1000
    
    # Detail view x-axis positions (percentages)
    detail_left_pos = 0
    detail_zero_pos = 50
    detail_call_end_pos = 75
    detail_right_pos = 100
    
    # Overview x-axis positions (percentages)
    overview_left_pos = 0
    overview_zero_pos = 30
    overview_call_end_pos = 60
    overview_right_pos = 100
    
    # Generate x-axis ticks data for detail view
    # First set up the major ticks
    x_ticks_detail = [
        {
            "id": "left-tick-detail",
            "position": detail_left_pos,
            "value": f"-{normal_window_size[0]:.1f} ms",
            "type": "major"
        },
        {
            "id": "zero-tick-detail",
            "position": detail_zero_pos,
            "value": "0.0 ms",
            "type": "major"
        },
        {
            "id": "call-end-tick-detail",
            "position": detail_call_end_pos,
            "value": f"{call_duration_ms:.1f} ms",
            "type": "major"
        },
        {
            "id": "right-tick-detail",
            "position": detail_right_pos,
            "value": f"+{normal_window_size[1]:.1f} ms",
            "type": "major"
        }
    ]
    
    # Add intermediate minor ticks
    # Between left and zero
    if detail_left_pos < detail_zero_pos:
        x_ticks_detail.append({
            "id": "minor-left-zero-detail",
            "position": (detail_left_pos + detail_zero_pos) / 2,
            "value": "",
            "type": "minor"
        })
    
    # Between zero and call-end
    if detail_zero_pos < detail_call_end_pos:
        x_ticks_detail.append({
            "id": "minor-zero-callend-detail",
            "position": (detail_zero_pos + detail_call_end_pos) / 2,
            "value": "",
            "type": "minor"
        })
    
    # Between call-end and right
    if detail_call_end_pos < detail_right_pos:
        x_ticks_detail.append({
            "id": "minor-callend-right-detail",
            "position": (detail_call_end_pos + detail_right_pos) / 2,
            "value": "",
            "type": "minor"
        })
    
    # Generate x-axis ticks data for overview
    x_ticks_overview = [
        {
            "id": "left-tick-overview",
            "position": overview_left_pos,
            "value": f"-{overview_window_size[0]:.1f} ms",
            "type": "major"
        },
        {
            "id": "zero-tick-overview",
            "position": overview_zero_pos,
            "value": "0.0 ms",
            "type": "major"
        },
        {
            "id": "call-end-tick-overview",
            "position": overview_call_end_pos,
            "value": f"{call_duration_ms:.1f} ms",
            "type": "major"
        },
        {
            "id": "right-tick-overview",
            "position": overview_right_pos,
            "value": f"+{overview_window_size[1]:.1f} ms",
            "type": "major"
        }
    ]
    
    # Add intermediate minor ticks for overview
    # Between left and zero
    if overview_left_pos < overview_zero_pos:
        x_ticks_overview.append({
            "id": "minor-left-zero-overview",
            "position": (overview_left_pos + overview_zero_pos) / 2,
            "value": "",
            "type": "minor"
        })
    
    # Between zero and call-end
    if overview_zero_pos < overview_call_end_pos:
        x_ticks_overview.append({
            "id": "minor-zero-callend-overview",
            "position": (overview_zero_pos + overview_call_end_pos) / 2,
            "value": "",
            "type": "minor"
        })
    
    # Between call-end and right
    if overview_call_end_pos < overview_right_pos:
        x_ticks_overview.append({
            "id": "minor-callend-right-overview",
            "position": (overview_call_end_pos + overview_right_pos) / 2,
            "value": "",
            "type": "minor"
        })
    
    # Generate y-axis ticks for frequency
    if not sample_rate:
        raise ValueError("Sample rate is required for spectrogram ticks")
        
    # Nyquist frequency (maximum possible frequency in the recording) is half the sample rate
    max_freq = sample_rate / 2 / 1000  # Convert to kHz
    
    # Increase the number of ticks for more granularity
    num_ticks = 11  # 0%, 10%, 20%, ..., 100%
    y_ticks = []
    
    # Generate main ticks
    for i in range(num_ticks):
        position = i * (100 / (num_ticks - 1))  # Positions from 0% to 100%
        value = max_freq - (max_freq * position / 100)  # Values from max_freq to 0 kHz
        
        # Add the tick with a size class for styling
        y_ticks.append({
            "position": position,
            "value": int(value),  # Integer values for cleaner display
            "type": "major"  # Mark as major tick for styling
        })
        
    # Add intermediate minor ticks between major ticks for extra precision
    if num_ticks > 2:  # Only add minor ticks if we have enough space
        for i in range(num_ticks - 1):
            # Calculate position halfway between major ticks
            position = (i * (100 / (num_ticks - 1))) + ((100 / (num_ticks - 1)) / 2)
            value = max_freq - (max_freq * position / 100)
            
            # Add minor tick (without displaying the value)
            y_ticks.append({
                "position": position,
                "value": "",  # No value displayed for minor ticks
                "type": "minor"  # Mark as minor tick for styling
            })
    
    return {
        "x_ticks_detail": x_ticks_detail,
        "x_ticks_overview": x_ticks_overview, 
        "y_ticks": y_ticks
    }


def process_pickle_file(pickle_file):
    """Process a pickle file that contains onset and offset data.
    
    Args:
        pickle_file: A file-like object containing pickle-serialized data
        
    Returns:
        tuple: (onsets, offsets) as lists of floats
        
    Raises:
        ValueError: If the pickle file format is not recognized or contains invalid data
        Exception: For any other errors during processing
    """
    try:
        # Load the pickle file
        pickle_data = pickle.load(pickle_file)

        # Extract onsets and offsets based on data format
        if isinstance(pickle_data, dict):
            onsets = pickle_data.get("onsets", [])
            offsets = pickle_data.get("offsets", [])
        elif isinstance(pickle_data, list) and len(pickle_data) >= 2:
            # Assume first item is onsets, second is offsets
            onsets = pickle_data[0]
            offsets = pickle_data[1]
        elif isinstance(pickle_data, tuple) and len(pickle_data) >= 2:
            # Assume first item is onsets, second is offsets
            onsets = pickle_data[0]
            offsets = pickle_data[1]
        else:
            # Unrecognized format
            logger.error(f"Pickle file format not recognized: {type(pickle_data)}")
            raise ValueError("Pickle file format not recognized. Expected a dictionary with 'onsets' and 'offsets' keys, or a list/tuple with at least 2 elements.")

        # Convert to lists if they're NumPy arrays or other iterables
        if isinstance(onsets, np.ndarray):
            onsets = onsets.tolist()
        elif not isinstance(onsets, list):
            onsets = list(onsets)

        if isinstance(offsets, np.ndarray):
            offsets = offsets.tolist()
        elif not isinstance(offsets, list):
            offsets = list(offsets)

        # Validate data
        if len(onsets) == 0 or len(offsets) == 0:
            raise ValueError("Pickle file does not contain required onset and offset lists.")

        # Check if lists are the same length
        if len(onsets) != len(offsets):
            raise ValueError("Onsets and offsets lists must have the same length.")
            
        # Convert numpy types to Python native types if needed
        onsets = [float(onset) for onset in onsets]
        offsets = [float(offset) for offset in offsets]
        
        return onsets, offsets

    except Exception as e:
        logger.error(f"Error processing pickle file: {str(e)}")
        logger.error(traceback.format_exc())
        raise


def auto_segment_audio(audio_path, min_duration_ms=10, smooth_window=3, threshold_factor=0.5, debug_visualization=False):
    """
    Automatically segment audio using the following steps:
    1. Take absolute value of the signal
    2. Smooth the signal using a moving average filter
    3. Apply a threshold to detect segments
    4. Reject markings shorter than the minimum duration
    
    Args:
        audio_path: Path to the audio file
        min_duration_ms: Minimum segment duration in milliseconds
        smooth_window: Window size for smoothing filter
        threshold_factor: Threshold factor (between 0-1) to apply
        debug_visualization: If True, generates a visualization of the segmentation process
        
    Returns:
        tuple: (onsets, offsets, [debug_path]) as lists of floats in seconds and optional debug image path
    """
    try:
        import soundfile as sf

        # Import visualization libraries if debug_visualization is enabled
        if debug_visualization:
            import matplotlib
            matplotlib.use('Agg')  # Use non-interactive backend
            import matplotlib.pyplot as plt
            import tempfile
            import os

        # Load the audio file
        audio_data, sample_rate = sf.read(audio_path)
        logger.info(f"Loaded audio file for automated segmentation: {audio_path}")
        logger.info(f"Audio shape: {audio_data.shape}, sample rate: {sample_rate}")
        
        # For stereo files, use the first channel for detection
        if len(audio_data.shape) > 1 and audio_data.shape[1] > 1:
            audio_data = audio_data[:, 0]
            logger.info(f"Using first channel from stereo recording for detection")
        
        # Step 1: Take absolute value of the signal
        abs_signal = np.abs(audio_data)
        
        # Step 2: Smooth the signal with a moving average filter
        if smooth_window > 1:
            kernel = np.ones(smooth_window) / smooth_window
            smoothed_signal = np.convolve(abs_signal, kernel, mode='same')
        else:
            smoothed_signal = abs_signal
        
        # Step 3: Apply threshold
        # Calculate adaptive threshold based on the signal statistics
        signal_mean = np.mean(smoothed_signal)
        signal_std = np.std(smoothed_signal)
        threshold = signal_mean + (threshold_factor * signal_std)
        
        logger.info(f"Auto-segmentation thresholds - Mean: {signal_mean:.6f}, Std: {signal_std:.6f}, Threshold: {threshold:.6f}")
        
        # Create binary mask where signal exceeds threshold
        binary_mask = smoothed_signal > threshold
        
        # Find transitions in the binary mask (0->1 and 1->0)
        # Transitions from 0->1 indicate segment onsets
        # Transitions from 1->0 indicate segment offsets
        transitions = np.diff(binary_mask.astype(int))
        onset_samples = np.where(transitions == 1)[0] + 1  # +1 because diff reduces length by 1
        offset_samples = np.where(transitions == -1)[0] + 1
        
        # Handle edge cases
        if binary_mask[0]:
            # Signal starts above threshold, insert onset at sample 0
            onset_samples = np.insert(onset_samples, 0, 0)
            
        if binary_mask[-1]:
            # Signal ends above threshold, append offset at the last sample
            offset_samples = np.append(offset_samples, len(binary_mask) - 1)
        
        # Ensure we have the same number of onsets and offsets
        if len(onset_samples) > len(offset_samples):
            # More onsets than offsets - trim extra onsets
            onset_samples = onset_samples[:len(offset_samples)]
        elif len(offset_samples) > len(onset_samples):
            # More offsets than onsets - trim extra offsets
            offset_samples = offset_samples[:len(onset_samples)]
            
        # Convert sample indices to time in seconds
        onsets = onset_samples / sample_rate
        offsets = offset_samples / sample_rate
        
        # Step 4: Reject segments shorter than the minimum duration
        min_samples = int((min_duration_ms / 1000) * sample_rate)
        valid_segments = []
        
        for i in range(len(onsets)):
            duration_samples = offset_samples[i] - onset_samples[i]
            if duration_samples >= min_samples:
                valid_segments.append(i)
        
        # Filter onsets and offsets to only include valid segments
        filtered_onsets = [onsets[i] for i in valid_segments]
        filtered_offsets = [offsets[i] for i in valid_segments]
        
        logger.info(f"Automated segmentation found {len(onsets)} potential segments")
        logger.info(f"After minimum duration filtering: {len(filtered_onsets)} segments")
        
        # Generate debug visualization if requested
        if debug_visualization:
            debug_path = None
            try:
                # Create a figure with multiple subplots
                fig, axes = plt.subplots(4, 1, figsize=(15, 12), sharex=True)
                
                # Time axis in seconds
                time_axis = np.arange(len(audio_data)) / sample_rate
                
                # 1. Plot the original signal
                axes[0].plot(time_axis, audio_data)
                axes[0].set_title('Original Signal')
                axes[0].set_ylabel('Amplitude')
                
                # 2. Plot the absolute signal
                axes[1].plot(time_axis, abs_signal)
                axes[1].set_title('Absolute Signal')
                axes[1].set_ylabel('Amplitude')
                
                # 3. Plot the smoothed signal with threshold
                axes[2].plot(time_axis, smoothed_signal)
                axes[2].axhline(y=threshold, color='r', linestyle='--', label=f'Threshold: {threshold:.6f}')
                axes[2].set_title(f'Smoothed Signal (window={smooth_window}) with Threshold (factor={threshold_factor})')
                axes[2].set_ylabel('Amplitude')
                axes[2].legend()
                
                # 4. Plot the binary mask with detected segments
                # Make sure binary_mask and time_axis have the same length for plotting
                if len(binary_mask) != len(time_axis):
                    logger.info(f"Fixing binary mask length for threshold plot: {len(binary_mask)} vs {len(time_axis)}")
                    if len(binary_mask) < len(time_axis):
                        # Pad binary mask if it's too short
                        padding = np.zeros(len(time_axis) - len(binary_mask))
                        binary_mask_plot = np.concatenate([binary_mask, padding])
                    else:
                        # Truncate binary mask if it's too long
                        binary_mask_plot = binary_mask[:len(time_axis)]
                else:
                    binary_mask_plot = binary_mask
                    
                axes[3].plot(time_axis, binary_mask_plot, label='Binary mask')
                
                # Add vertical lines for onsets (green) and offsets (red)
                for onset in filtered_onsets:
                    axes[3].axvline(x=onset, color='g', linestyle='--')
                    
                for offset in filtered_offsets:
                    axes[3].axvline(x=offset, color='r', linestyle='-.')
                    
                # Marking segments that were filtered out (too short)
                for i in range(len(onsets)):
                    if i not in valid_segments:
                        # Draw a light red box over rejected segments
                        axes[3].axvspan(onsets[i], offsets[i], alpha=0.2, color='red')
                
                axes[3].set_title(f'Binary Mask with Detected Segments (min duration={min_duration_ms}ms)')
                axes[3].set_xlabel('Time (s)')
                axes[3].set_ylabel('State (0/1)')
                
                # Adjust layout
                plt.tight_layout()
                
                # Save to a temporary file
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                    debug_path = tmp_file.name
                    plt.savefig(debug_path, dpi=100)
                    plt.close()
                
                # Log the debug file location
                logger.info(f"Created segmentation debug visualization at {debug_path}")
                
            except Exception as viz_error:
                logger.error(f"Error creating debug visualization: {str(viz_error)}")
                logger.error(traceback.format_exc())
                # If there's an error with visualization, still return the segments
            
            return filtered_onsets, filtered_offsets, debug_path
        
        # Return without visualization path if debug_visualization is False
        return filtered_onsets, filtered_offsets
        
    except Exception as e:
        logger.error(f"Error in auto_segment_audio: {str(e)}")
        logger.error(traceback.format_exc())
        raise


def energy_based_segment_audio(audio_path, min_duration_ms=10, smooth_window=3, threshold_factor=0.5, debug_visualization=False):
    """
    Segment audio based on energy levels using the following steps:
    1. Calculate the short-time energy of the signal
    2. Smooth the energy curve
    3. Apply an adaptive threshold based on the energy statistics
    4. Reject markings shorter than the minimum duration
    
    Args:
        audio_path: Path to the audio file
        min_duration_ms: Minimum segment duration in milliseconds
        smooth_window: Window size for smoothing filter
        threshold_factor: Threshold factor (between 0-1) to apply to energy detection
        debug_visualization: If True, generates a visualization of the segmentation process
        
    Returns:
        tuple: (onsets, offsets, [debug_path]) as lists of floats in seconds and optional debug image path
    """
    try:
        import soundfile as sf

        # Import visualization libraries if debug_visualization is enabled
        if debug_visualization:
            import matplotlib
            matplotlib.use('Agg')  # Use non-interactive backend
            import matplotlib.pyplot as plt
            import tempfile
            import os

        # Load the audio file
        audio_data, sample_rate = sf.read(audio_path)
        logger.info(f"Loaded audio file for energy-based segmentation: {audio_path}")
        logger.info(f"Audio shape: {audio_data.shape}, sample rate: {sample_rate}")
        
        # For stereo files, use the first channel for detection
        if len(audio_data.shape) > 1 and audio_data.shape[1] > 1:
            audio_data = audio_data[:, 0]
            logger.info(f"Using first channel from stereo recording for detection")
        
        # Step 1: Calculate short-time energy
        # Set the frame size for energy calculation (adjust based on expected call frequency)
        frame_size = int(0.01 * sample_rate)  # 10ms frames
        energy = np.zeros(len(audio_data) // frame_size)
        
        for i in range(len(energy)):
            # Calculate energy for each frame
            start = i * frame_size
            end = min(start + frame_size, len(audio_data))
            frame = audio_data[start:end]
            # Energy is sum of squared amplitudes
            energy[i] = np.sum(frame ** 2) / len(frame)
        
        # Interpolate energy back to signal length for easier visualization
        energy_full = np.interp(
            np.linspace(0, len(energy), len(audio_data)), 
            np.arange(len(energy)), 
            energy
        )
        
        # Step 2: Smooth the energy curve with a moving average filter
        if smooth_window > 1:
            kernel = np.ones(smooth_window) / smooth_window
            smoothed_energy = np.convolve(energy_full, kernel, mode='same')
        else:
            smoothed_energy = energy_full
        
        # Step 3: Apply threshold 
        # Calculate adaptive threshold based on the energy statistics
        energy_mean = np.mean(smoothed_energy)
        energy_std = np.std(smoothed_energy)
        threshold = energy_mean + (threshold_factor * energy_std)
        
        logger.info(f"Energy segmentation thresholds - Mean: {energy_mean:.6f}, Std: {energy_std:.6f}, Threshold: {threshold:.6f}")
        
        # Create binary mask where energy exceeds threshold
        binary_mask = smoothed_energy > threshold
        
        # Find transitions in the binary mask (0->1 and 1->0)
        transitions = np.diff(binary_mask.astype(int))
        onset_samples = np.where(transitions == 1)[0] + 1  # +1 because diff reduces length by 1
        offset_samples = np.where(transitions == -1)[0] + 1
        
        # Handle edge cases
        if binary_mask[0]:
            # Signal starts above threshold, insert onset at sample 0
            onset_samples = np.insert(onset_samples, 0, 0)
            
        if binary_mask[-1]:
            # Signal ends above threshold, append offset at the last sample
            offset_samples = np.append(offset_samples, len(binary_mask) - 1)
        
        # Ensure we have the same number of onsets and offsets
        if len(onset_samples) > len(offset_samples):
            # More onsets than offsets - trim extra onsets
            onset_samples = onset_samples[:len(offset_samples)]
        elif len(offset_samples) > len(onset_samples):
            # More offsets than onsets - trim extra offsets
            offset_samples = offset_samples[:len(onset_samples)]
            
        # Convert sample indices to time in seconds
        onsets = onset_samples / sample_rate
        offsets = offset_samples / sample_rate
        
        # Step 4: Reject segments shorter than the minimum duration
        min_samples = int((min_duration_ms / 1000) * sample_rate)
        valid_segments = []
        
        for i in range(len(onsets)):
            duration_samples = offset_samples[i] - onset_samples[i]
            if duration_samples >= min_samples:
                valid_segments.append(i)
        
        # Filter onsets and offsets to only include valid segments
        filtered_onsets = [onsets[i] for i in valid_segments]
        filtered_offsets = [offsets[i] for i in valid_segments]
        
        logger.info(f"Energy-based segmentation found {len(onsets)} potential segments")
        logger.info(f"After minimum duration filtering: {len(filtered_onsets)} segments")
        
        # Generate debug visualization if requested
        if debug_visualization:
            debug_path = None
            try:
                # Create a figure with multiple subplots
                fig, axes = plt.subplots(4, 1, figsize=(15, 12), sharex=True)
                
                # Time axis in seconds
                time_axis = np.arange(len(audio_data)) / sample_rate
                
                # 1. Plot the original signal
                axes[0].plot(time_axis, audio_data)
                axes[0].set_title('Original Signal')
                axes[0].set_ylabel('Amplitude')
                
                # 2. Plot the energy curve
                axes[1].plot(time_axis, energy_full)
                axes[1].set_title('Energy')
                axes[1].set_ylabel('Energy')
                
                # 3. Plot the smoothed energy with threshold
                axes[2].plot(time_axis, smoothed_energy)
                axes[2].axhline(y=threshold, color='r', linestyle='--', label=f'Threshold: {threshold:.6f}')
                axes[2].set_title(f'Smoothed Energy (window={smooth_window}) with Threshold (factor={threshold_factor})')
                axes[2].set_ylabel('Energy')
                axes[2].legend()
                
                # 4. Plot the binary mask with detected segments
                # Make sure binary_mask and time_axis have the same length for plotting
                if len(binary_mask) != len(time_axis):
                    logger.info(f"Fixing binary mask length for energy plot: {len(binary_mask)} vs {len(time_axis)}")
                    if len(binary_mask) < len(time_axis):
                        # Pad binary mask if it's too short
                        padding = np.zeros(len(time_axis) - len(binary_mask))
                        binary_mask_plot = np.concatenate([binary_mask, padding])
                    else:
                        # Truncate binary mask if it's too long
                        binary_mask_plot = binary_mask[:len(time_axis)]
                else:
                    binary_mask_plot = binary_mask
                    
                axes[3].plot(time_axis, binary_mask_plot, label='Binary mask')
                
                # Add vertical lines for onsets (green) and offsets (red)
                for onset in filtered_onsets:
                    axes[3].axvline(x=onset, color='g', linestyle='--')
                    
                for offset in filtered_offsets:
                    axes[3].axvline(x=offset, color='r', linestyle='-.')
                    
                # Marking segments that were filtered out (too short)
                for i in range(len(onsets)):
                    if i not in valid_segments:
                        # Draw a light red box over rejected segments
                        axes[3].axvspan(onsets[i], offsets[i], alpha=0.2, color='red')
                
                axes[3].set_title(f'Binary Mask with Detected Segments (min duration={min_duration_ms}ms)')
                axes[3].set_xlabel('Time (s)')
                axes[3].set_ylabel('State (0/1)')
                
                # Adjust layout
                plt.tight_layout()
                
                # Save to a temporary file
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                    debug_path = tmp_file.name
                    plt.savefig(debug_path, dpi=100)
                    plt.close()
                
                # Log the debug file location
                logger.info(f"Created energy segmentation debug visualization at {debug_path}")
                
            except Exception as viz_error:
                logger.error(f"Error creating debug visualization: {str(viz_error)}")
                logger.error(traceback.format_exc())
                # If there's an error with visualization, still return the segments
            
            return filtered_onsets, filtered_offsets, debug_path
        
        # Return without visualization path if debug_visualization is False
        return filtered_onsets, filtered_offsets
        
    except Exception as e:
        logger.error(f"Error in energy_based_segment_audio: {str(e)}")
        logger.error(traceback.format_exc())
        raise
