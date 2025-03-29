"""
Celery tasks for BattyCoda audio and spectrogram processing.

DEPRECATED: This file is deprecated and will be moved to specialized modules 
in the task_modules directory. This file now re-exports functions for backward 
compatibility.

The functionality has been moved to the following modules:
- task_modules/base.py: Common utilities
- task_modules/spectrogram_tasks.py: Spectrogram generation tasks
- task_modules/detection_tasks.py: Call detection tasks
- task_modules/segmentation_tasks.py: Auto-segmentation tasks
"""

# Re-export functions from specialized modules
from .task_modules.base import extract_audio_segment, log_performance, logger
from .task_modules.detection_tasks import run_call_detection, run_dummy_classifier
from .task_modules.segmentation_tasks import auto_segment_recording_task
from .task_modules.spectrogram_tasks import (
    generate_recording_spectrogram,
    generate_spectrogram,
    generate_spectrogram_task,
    prefetch_spectrograms,
)

# Export all functions with their original names
__all__ = [
    "log_performance",
    "extract_audio_segment",
    "generate_spectrogram_task",
    "prefetch_spectrograms",
    "generate_recording_spectrogram",
    "run_call_detection",
    "run_dummy_classifier",
    "auto_segment_recording_task",
    "generate_spectrogram",
]
