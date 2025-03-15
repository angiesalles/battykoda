"""
Utility functions for BattyCoda application.
Contains common functions used across multiple files.
"""
import os
import platform
import getpass

def get_home_directory():
    """
    Get the appropriate home directory based on the OS.
    
    Returns:
        str: The home directory path segment ("Users" for macOS, "home" for Linux/Others)
    """
    # Check if running on Replit
    if os.environ.get('REPL_SLUG') or os.environ.get('REPL_ID'):
        return "home"  # Always use "home" on Replit
    elif platform.system() == "Darwin":  # macOS
        return "Users"
    elif platform.system() == "Windows":
        return "home"  # Use 'home' for URL paths on Windows
    else:  # Linux
        return "home"

def get_user_directory():
    """
    Get the current user's directory.
    
    Returns:
        str: The current user's username
    """
    return getpass.getuser()

def convert_path_to_os_specific(path):
    """
    Convert a URL path to an OS-specific file path.
    
    Args:
        path (str): The URL path (e.g., "home/username/species/file.wav")
        
    Returns:
        str: OS-specific path (e.g., "Users/username/species/file.wav" on macOS)
    """
    home_dir = get_home_directory()
    if 'home/' in path:
        return path.replace('home/', home_dir + '/')
    return path

def is_folder_exists(osfolder, path):
    """
    Check if a folder exists at the given path.
    
    Args:
        osfolder (str): OS-specific folder prefix
        path (str): The path to check
        
    Returns:
        bool: True if the folder exists, False otherwise
    """
    return os.path.isdir(osfolder + path)

def is_file_exists(osfolder, path):
    """
    Check if a file exists at the given path.
    
    Args:
        osfolder (str): OS-specific folder prefix
        path (str): The path to check
        
    Returns:
        bool: True if the file exists, False otherwise
    """
    return os.path.isfile(osfolder + path)