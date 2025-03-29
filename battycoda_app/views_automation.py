"""
Views for automation in the BattyCoda application.

DEPRECATED: This file is deprecated and will be moved to specialized modules 
in the views_automation directory. This file now re-exports functions for backward 
compatibility.

The functionality has been moved to the following modules:
- views_automation/runs_management.py: Basic CRUD operations for detection runs
- views_automation/runs_details.py: Detailed views for viewing detection run results
- views_automation/task_creation.py: Creating tasks from detection runs
- views_automation/results_application.py: Applying detection results to segments
"""

from .views_automation.results_application import apply_detection_results_view
from .views_automation.runs_details import detection_run_detail_view, detection_run_status_view

# Re-export all views for backwards compatibility
from .views_automation.runs_management import (
    automation_home_view,
    create_detection_run_view,
    delete_detection_run_view,
    detection_run_list_view,
)
from .views_automation.task_creation import create_task_batch_from_detection_run
