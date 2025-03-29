"""
Utility functions for the battycoda application.

DEPRECATED: This file is deprecated and will be moved to specialized modules
in the utils_modules directory. This file now re-exports functions for backward
compatibility.

The functionality has been moved to the following modules:
- utils_modules/path_utils.py: Functions for file path handling
- utils_modules/species_utils.py: Functions for species data management
- utils_modules/recording_utils.py: Functions for working with recordings
- utils_modules/demo_utils.py: Functions for creating demo data
"""

from .utils_modules.demo_utils import create_demo_task_batch

# Re-export all utilities for backwards compatibility
from .utils_modules.path_utils import convert_path_to_os_specific
from .utils_modules.recording_utils import create_recording_from_batch
from .utils_modules.species_utils import available_species, import_default_species
