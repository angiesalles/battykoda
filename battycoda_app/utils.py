"""
Utility functions for the battycoda application.
"""
import os
import platform
import logging
import shutil
import subprocess
from django.conf import settings

# Set up logging
logger = logging.getLogger('battycoda.utils')

def get_home_directory():
    """
    Get the system home directory based on platform
    
    Returns:
        str: Path to the home directory
    """
    if platform.system() == "Windows":
        return "Users"
    else:
        return "home"
        
def get_template_directory():
    """
    Find the template directory for user directory creation and species templates
    
    Returns:
        str: Path to the template directory, or None if not found
    """
    # List of possible template directory locations
    template_dirs = [
        '/template',              # Docker mount (primary)
        '/app/template',          # Project directory in Docker
        os.path.join(settings.BASE_DIR, 'template'),  # Django project base
        '/home/ubuntu/template'   # Host system location
    ]
    
    # Try each location
    for template_dir in template_dirs:
        if os.path.exists(template_dir):
            logger.info(f"Found template directory at: {template_dir}")
            return template_dir
            
    # No template directory found
    logger.warning("No template directory found in any location")
    return None

def convert_path_to_os_specific(path):
    """
    Convert a web path to an OS-specific path
    
    Args:
        path (str): Web path (like "home/username/folder")
        
    Returns:
        str: OS-specific path to the location in media directory
    """
    # Normalize directory separators
    path = path.replace('\\', '/')
    
    # Remove leading slash if present
    if path.startswith('/'):
        path = path[1:]
    
    # All user paths now go to media folder
    return os.path.join(settings.MEDIA_ROOT, path)

def ensure_user_directory_exists(username):
    """
    Ensure that a user's home directory exists, create it if it doesn't
    
    Args:
        username (str): Username to check/create directory for
        
    Returns:
        bool: True if directory exists or was created
    """
    # Get template directory
    template_dir = '/template'
    
    # Store user directories in media folder (shared between containers)
    user_home_path = os.path.join(settings.MEDIA_ROOT, 'home', username)
    
    # Return if directory already exists
    if os.path.exists(user_home_path):
        return True
    
    # Create the directory
    logger.info(f"Creating user home directory: {user_home_path}")
    os.makedirs(user_home_path, exist_ok=True)
    
    # Copy template content
    for item in os.listdir(template_dir):
        source = os.path.join(template_dir, item)
        destination = os.path.join(user_home_path, item)
        
        if os.path.isdir(source):
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
    
    # Set permissions to make directories writable by everyone
    subprocess.run(['chmod', '-R', '777', user_home_path])
    logger.info(f"Set permissions for {user_home_path}")
    
    return True

def available_species():
    """
    Get a list of available species templates
    
    Returns:
        list: List of species template names
    """
    try:
        # Get template directory
        template_dir = get_template_directory()
        if not template_dir:
            logger.warning("Cannot list available species: No template directory found")
            return []
        
        # Get list of directories in template
        species_list = [item for item in os.listdir(template_dir) 
                       if os.path.isdir(os.path.join(template_dir, item)) 
                       and not item.startswith('.')]
        
        return sorted(species_list)
    
    except Exception as e:
        logger.error(f"Error getting available species: {str(e)}")
        return []