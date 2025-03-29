"""
Automation view modules for the BattyCoda application.

This package contains views related to automatic detection and classification:
- runs_management: Basic CRUD operations for detection runs
- runs_details: Detailed views for viewing detection run results
- task_creation: Creating tasks from detection runs
- results_application: Applying detection results to segments
"""

from .results_application import apply_detection_results_view
from .runs_details import detection_run_detail_view, detection_run_status_view

# Re-export all views for backwards compatibility
from .runs_management import (
    automation_home_view,
    create_detection_run_view,
    delete_detection_run_view,
    detection_run_list_view,
)
from .task_creation import create_task_batch_from_detection_run

# Export all functions with their original names
__all__ = [
    # Runs management
    "automation_home_view",
    "detection_run_list_view",
    "create_detection_run_view",
    "delete_detection_run_view",
    # Runs details
    "detection_run_detail_view",
    "detection_run_status_view",
    # Task creation
    "create_task_batch_from_detection_run",
    # Results application
    "apply_detection_results_view",
]
