"""
Task-related views for the battycoda application.
This file serves as a central import point for all task-related view functions
that have been organized into separate modules for better maintainability.
"""

# Import views from individual modules
from .views_task_listing import (
    task_list_view,
    task_detail_view,
    create_task_view
)

from .views_task_batch import (
    task_batch_list_view,
    task_batch_detail_view,
    create_task_batch_view
)

from .views_task_navigation import (
    get_next_task_from_batch_view,
    get_next_task_view,
    get_last_task_view
)

from .views_task_annotation import (
    task_annotation_view
)

from .views_task_legacy import (
    wav_file_view,
    task_status_view
)

# Export all views to maintain compatibility with existing URL patterns
__all__ = [
    'task_list_view',
    'task_detail_view',
    'create_task_view',
    'task_batch_list_view',
    'task_batch_detail_view',
    'create_task_batch_view',
    'get_next_task_from_batch_view',
    'get_next_task_view',
    'get_last_task_view',
    'task_annotation_view',
    'wav_file_view',
    'task_status_view'
]