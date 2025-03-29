"""
Base utilities for BattyCoda audio processing tasks.
"""
import logging
import os
import time
import traceback

from django.conf import settings

# Configure logging
logger = logging.getLogger("battycoda.tasks")


def log_performance(start_time, message):
    """Log performance with elapsed time - only for total task time"""
    # Only log total task completions to reduce log volume
    if "TOTAL" in message:
        elapsed = time.time() - start_time
        logger.info(f"PERF: {message} - {elapsed:.3f}s")


def extract_audio_segment(wav_path, onset, offset, padding=0.01):
    """
    Extract a segment of audio from a WAV file.

    Args:
        wav_path: Path to the WAV file
        onset: Start time in seconds
        offset: End time in seconds
        padding: Optional padding in seconds to add before/after segment

    Returns:
        numpy.ndarray: Audio segment data
    """
    try:
        # Load the audio file
        import soundfile as sf

        audio_data, sample_rate = sf.read(wav_path)

        # Log file information
        logger.info(f"Loaded audio file {wav_path}: {len(audio_data)} samples, {sample_rate}Hz")

        # Calculate sample indices with padding
        start_sample = max(0, int((onset - padding) * sample_rate))
        end_sample = min(len(audio_data), int((offset + padding) * sample_rate))

        # Log segment bounds
        logger.info(f"Extracting segment from {onset-padding:.4f}s to {offset+padding:.4f}s")
        logger.info(f"Sample indices: {start_sample} to {end_sample} (length: {end_sample-start_sample})")

        # Extract the segment
        segment = audio_data[start_sample:end_sample]

        return segment
    except Exception as e:
        logger.error(f"Error extracting audio segment: {str(e)}")
        logger.error(f"File: {wav_path}, Onset: {onset}, Offset: {offset}")
        logger.error(traceback.format_exc())
        raise
