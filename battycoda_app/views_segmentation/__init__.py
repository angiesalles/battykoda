"""
Segmentation view modules for the BattyCoda application.

This package contains views related to audio recording segmentation, organized by function:
- segment_management: Basic CRUD operations for segments
- segmentation_execution: Running automated segmentation algorithms
- segmentation_batches: Batch operations for segmentation
- segmentation_import: Importing segments from external sources
- segmentation_settings: Configuration of segmentation settings
"""

# Re-export all views for backwards compatibility
from .segment_management import add_segment_view, delete_segment_view, edit_segment_view, segment_recording_view
from .segmentation_batches import batch_segmentation_view, segmentation_jobs_status_view
from .segmentation_execution import auto_segment_recording_view, auto_segment_status_view
from .segmentation_import import upload_pickle_segments_view
from .segmentation_settings import activate_segmentation_view

# Export all functions with their original names
__all__ = [
    # Segment management
    "segment_recording_view",
    "add_segment_view",
    "edit_segment_view",
    "delete_segment_view",
    # Segmentation batches
    "batch_segmentation_view",
    "segmentation_jobs_status_view",
    # Segmentation execution
    "auto_segment_recording_view",
    "auto_segment_status_view",
    # Segmentation import
    "upload_pickle_segments_view",
    # Segmentation settings
    "activate_segmentation_view",
]
