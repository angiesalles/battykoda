"""
Utility modules for the BattyCoda application.

This package contains utility functions organized by purpose:
- path_utils: Functions for file path handling
- species_utils: Functions for species data management
- recording_utils: Functions for working with recordings
- demo_utils: Functions for creating demo data
"""

from .demo_utils import create_demo_task_batch

# Re-export all utilities for backwards compatibility
from .path_utils import convert_path_to_os_specific
from .recording_utils import create_recording_from_batch
from .species_utils import available_species, import_default_species

# Export all functions with their original names
__all__ = [
    # Path utilities
    "convert_path_to_os_specific",
    # Species utilities
    "available_species",
    "import_default_species",
    # Recording utilities
    "create_recording_from_batch",
    # Demo utilities
    "create_demo_task_batch",
]
