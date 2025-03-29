"""
Core audio processing functions for BattyCoda.
"""
import logging
import traceback

# Configure logging
logger = logging.getLogger("battycoda.audio.processing")


def normal_hwin():
    """Returns the window padding as (pre_window, post_window) in milliseconds."""
    return (8, 8)


def overview_hwin():
    """Returns the window padding as (pre_window, post_window) in milliseconds."""
    return (150, 350)


def get_audio_bit(audio_path, call_number, window_size, extra_params=None):
    """
    Get a specific bit of audio containing a bat call.
    Primary method: Use onset/offset from Task model (passed in extra_params)
    Legacy method: Pull call data from paired pickle file (only used during TaskBatch creation)

    Args:
        audio_path: Path to the WAV file
        call_number: Which call to extract (only used for legacy pickle method)
        window_size: Size of the window around the call in milliseconds (when passed from normal_hwin/overview_hwin)
        extra_params: Dictionary of extra parameters like onset/offset from Task model

    Returns:
        tuple: (audio_data, sample_rate, hash_string)
    """
    try:
        import hashlib
        import os

        import numpy as np

        # Calculate file hash based on path (for consistency across containers)
        file_hash = hashlib.md5(audio_path.encode()).hexdigest()

        # Check if audio file exists - no alternative paths, just fail if not found
        if not os.path.exists(audio_path):
            logger.error(f"Audio file not found: {audio_path}")
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # If we have onset/offset data, use extract_audio_segment
        if extra_params and "onset" in extra_params and "offset" in extra_params:
            # Use onset/offset provided in parameters
            onset_time = float(extra_params["onset"])
            offset_time = float(extra_params["offset"])

            # Handle window padding (in seconds)
            pre_padding = window_size[0] / 1000  # convert ms to seconds
            post_padding = window_size[1] / 1000

            # Import the extract_audio_segment function
            from ..task_modules.base import extract_audio_segment

            # Calculate the padded segment boundaries - no need to clamp values
            # as extract_audio_segment will handle out-of-bounds conditions
            start_time = onset_time - pre_padding
            end_time = offset_time + post_padding

            # Use the optimized extract_audio_segment function
            segment, sample_rate = extract_audio_segment(audio_path, start_time, end_time)

            # Handle adding second channel for stereo (if needed)
            if segment.shape[1] == 1:
                segment = np.column_stack((segment, segment))

            # Normalize audio data (only the segment)
            std = np.std(segment)
            if std > 0:
                segment /= std

            return segment, sample_rate, file_hash
        else:
            # Legacy path for cases without onset/offset (should be rare)
            logger.warning("No onset/offset provided, falling back to reading entire file (inefficient)")

            # Import the extract_audio_segment function
            from ..task_modules.base import extract_audio_segment

            # Read the entire file (0 to None means start to end)
            audiodata, sample_rate = extract_audio_segment(audio_path, 0, None)

            # Handle adding second channel for stereo (if needed)
            if audiodata.shape[1] == 1:
                audiodata = np.column_stack((audiodata, audiodata))

            # Normalize audio data
            std = np.std(audiodata)
            if std > 0:
                audiodata /= std

            return audiodata, sample_rate, file_hash
    except Exception as e:
        logger.error(f"Error in get_audio_bit: {str(e)}")
        logger.debug(traceback.format_exc())
        return None, 0, ""


# Missing imports
import os
