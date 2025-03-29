"""
Utility functions for file handling and caching in BattyCoda audio processing.
"""
import logging
import os
import pickle

from django.conf import settings

# Configure logging
logger = logging.getLogger("battycoda.audio.file_utils")


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
        import numpy as np

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
            raise ValueError(
                "Pickle file format not recognized. Expected a dictionary with 'onsets' and 'offsets' keys, or a list/tuple with at least 2 elements."
            )

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
        import traceback

        logger.error(traceback.format_exc())
        raise
