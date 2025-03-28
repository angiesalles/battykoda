"""
Utility functions for audio processing in BattyCoda.

This module re-exports functions from the specialized audio modules
to maintain backward compatibility with existing code.
"""
import logging

# Configure logging
logger = logging.getLogger("battycoda.audio")

# Re-export functions from specialized modules
from .modules.file_utils import appropriate_file, process_pickle_file
from .modules.audio_processing import get_audio_bit, normal_hwin, overview_hwin
from .modules.visualization import (
    get_spectrogram_ticks, 
    auto_segment_audio, 
    energy_based_segment_audio
)

# Export all functions with their original names
__all__ = [
    'appropriate_file',
    'process_pickle_file',
    'get_audio_bit',
    'normal_hwin',
    'overview_hwin',
    'get_spectrogram_ticks',
    'auto_segment_audio',
    'energy_based_segment_audio',
]