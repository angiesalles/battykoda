"""
Test settings for the Battycoda project.
"""

from unittest.mock import MagicMock, patch

# Patch generate_spectrograms to do nothing
generate_spectrograms_patch = patch("battycoda_app.models.Task.generate_spectrograms", MagicMock(return_value=None))

# Patch import_default_species to return empty list
import_default_species_patch = patch(
    "battycoda_app.utils_modules.species_utils.import_default_species", MagicMock(return_value=[])
)

# Patch file operations
file_operations_patch = patch(
    "django.core.files.storage.FileSystemStorage._save", MagicMock(return_value="test_file.txt")
)

# Patch directory creation
makedirs_patch = patch("os.makedirs", MagicMock(return_value=None))

# Patch file existence check
path_exists_patch = patch("os.path.exists", MagicMock(return_value=True))

# Patch open file operations
open_file_patch = patch("builtins.open", MagicMock())

# Patch File class
file_class_patch = patch("django.core.files.File", MagicMock())

# Use an in-memory SQLite database for tests
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Use a temporary directory for media files during tests
import tempfile

MEDIA_ROOT = tempfile.mkdtemp()

# Disable Celery tasks during tests
CELERY_TASK_ALWAYS_EAGER = True

# All patches to be applied
all_patches = [
    generate_spectrograms_patch,
    import_default_species_patch,
    file_operations_patch,
    makedirs_patch,
    path_exists_patch,
    open_file_patch,
    file_class_patch,
]
