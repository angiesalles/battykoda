"""
Utility functions for BattyCoda application.
Contains common functions used across multiple files.
"""
import os
import platform
from functools import wraps
from flask import redirect, url_for

# Import the debug utility for easy access
from utils.debug import try_connect_debugger


def find_case_insensitive_path(path):
    """
    Find the correct case-sensitive path in the filesystem using a case-insensitive search.
    
    Args:
        path (str): A path that might not match the filesystem case exactly
        
    Returns:
        str: The correct case-sensitive path if found, or the original path if not found
    """
    # If the path exists as is, return it
    if os.path.exists(path):
        return path
        
    # Split the path into components
    head, tail = os.path.split(path)
    
    # If we've reached the filesystem root, return the original path
    if not head or head == path:
        return path
    
    # Find the correct case for the parent directory
    head = find_case_insensitive_path(head)
    
    # Now look for a case-insensitive match for the current component
    if os.path.exists(head):
        # Get the directories/files in the parent directory
        entries = os.listdir(head)

        # Look for a case-insensitive match
        for entry in entries:
            if entry.lower() == tail.lower():
                # Found a match with the correct case
                return os.path.join(head, entry)

    # No match found, return the original tail with the corrected head
    return os.path.join(head, tail)


def get_home_directory():
    """
    Get the appropriate home directory based on the OS.

    Returns:
        str: The home directory path segment ("Users" for macOS, "home" for Linux/Others)
    """
    # Check if running on Replit
    if platform.system() == "Darwin":  # macOS
        return "/Users"
    elif platform.system() == "Windows":
        return "C:/Users"  # Use 'home' for URL paths on Windows
    else:  # Linux
        return "/home"

def convert_path_to_os_specific(path):
    """
    Convert a URL path to an OS-specific file path with case correction.
    
    Args:
        path (str): The URL path (e.g., "home/username/species/file.wav")
        
    Returns:
        str: OS-specific path (e.g., "/Users/username/species/file.wav" on macOS)
    """
    home_dir = get_home_directory()
    
    # Basic path conversion
    os_path = home_dir + path[4:]

    # Try to get the correct case on case-sensitive filesystems
    if platform.system() != "Windows":  # Windows is case-insensitive by default
        return find_case_insensitive_path(os_path)
    else:
        return os_path
