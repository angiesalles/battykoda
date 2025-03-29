"""
Path utility functions for handling file paths.
"""

import os

from django.conf import settings


def convert_path_to_os_specific(path):
    """
    Convert a web path to an OS-specific path

    Args:
        path (str): Web path (like "recordings/audio.wav")

    Returns:
        str: OS-specific path to the location in media directory
    """
    # Normalize directory separators
    path = path.replace("\\", "/")

    # Remove leading slash if present
    if path.startswith("/"):
        path = path[1:]

    # All paths now go to media folder
    return os.path.join(settings.MEDIA_ROOT, path)
