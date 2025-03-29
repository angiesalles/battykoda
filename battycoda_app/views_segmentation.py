"""
Views for segmentation of audio recordings.

DEPRECATED: This file is deprecated and will be moved to specialized modules 
in the views_segmentation directory. This file now re-exports functions for backward 
compatibility.

The functionality has been moved to the following modules:
- views_segmentation/segment_management.py: Basic CRUD operations for segments
- views_segmentation/segmentation_execution.py: Running automated segmentation algorithms
- views_segmentation/segmentation_batches.py: Batch operations for segmentation
- views_segmentation/segmentation_import.py: Importing segments from external sources
- views_segmentation/segmentation_settings.py: Configuration of segmentation settings
"""

# Re-export all views for backwards compatibility
from .views_segmentation.segment_management import (
    add_segment_view,
    delete_segment_view,
    edit_segment_view,
    segment_recording_view,
)
from .views_segmentation.segmentation_batches import batch_segmentation_view, segmentation_jobs_status_view
from .views_segmentation.segmentation_execution import auto_segment_recording_view, auto_segment_status_view
from .views_segmentation.segmentation_import import upload_pickle_segments_view
from .views_segmentation.segmentation_settings import activate_segmentation_view

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
