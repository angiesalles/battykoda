"""
DEPRECATED: This file is deprecated and will be removed in a future version.
All functionality has been moved to specialized modules:

- views_recording_core.py: Core recording CRUD operations
- views_segmentation.py: All segmentation-related functionality
- views_audio_streaming.py: Audio streaming functionality
- views_tasks.py: Tasks and spectrograms functionality

This file only re-exports functions for backward compatibility.
"""

# Re-export helper function
# Re-export from audio streaming module
from .views_audio_streaming import get_audio_waveform_data, stream_audio_view, streaming_file_iterator

# Re-export from recording core module
from .views_recording_core import (
    create_recording_view,
    delete_recording_view,
    edit_recording_view,
    recording_detail_view,
    recording_list_view,
)

# Re-export from segmentation module
from .views_segmentation import (
    activate_segmentation_view,
    add_segment_view,
    auto_segment_recording_view,
    auto_segment_status_view,
    batch_segmentation_view,
    delete_segment_view,
    edit_segment_view,
    segment_recording_view,
    segmentation_jobs_status_view,
    upload_pickle_segments_view,
)

# Re-export from tasks module
from .views_tasks import create_tasks_from_segments_view, recording_spectrogram_status_view
