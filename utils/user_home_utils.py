"""
Utilities for working with Docker user home directories.

These utilities help create and manage user home directories in the Docker container,
especially for Cloudflare authenticated users.
"""

import os
import logging
import shutil
import subprocess
from pathlib import Path

# Set up logging
logger = logging.getLogger('battycoda.utils.user_home')

def create_user_home_path(username, template_dir=None):
    """
    Create a user's home directory (/home/username) in the Docker container
    and populate it with template content.
    
    Args:
        username (str): Username to create directory for
        template_dir (str, optional): Path to template directory
                                      (defaults to /template if None)
        
    Returns:
        bool: True if directory was created successfully, False otherwise
    """
    # Determine paths
    if template_dir is None:
        template_dir = '/template' if os.path.exists('/template') else '/app/template'
    
    # Ensure template directory exists
    if not os.path.exists(template_dir):
        logger.error(f"Template directory not found: {template_dir}")
        return False
    
    try:
        # Create base user directory in /home
        user_home_path = os.path.join('/home', username)
        
        # Check if the directory already exists
        if os.path.exists(user_home_path):
            logger.info(f"User home directory already exists: {user_home_path}")
            return True
        
        # Create the user directory
        os.makedirs(user_home_path, exist_ok=True)
        logger.info(f"Created user home directory: {user_home_path}")
        
        # Copy template content recursively
        for item in os.listdir(template_dir):
            source = os.path.join(template_dir, item)
            destination = os.path.join(user_home_path, item)
            
            if os.path.isdir(source):
                shutil.copytree(source, destination)
                logger.info(f"Copied directory: {source} -> {destination}")
            else:
                shutil.copy2(source, destination)
                logger.info(f"Copied file: {source} -> {destination}")
        
        # Set proper ownership
        # We can't use os.chown in Docker as the Python process doesn't have permission
        # to change ownership, so we'll use subprocess to run chmod/chown if needed
        try:
            subprocess.run(['chmod', '-R', '755', user_home_path])
            # Try to set ownership to the username if it exists as a user
            subprocess.run(['chown', '-R', f'{username}:{username}', user_home_path])
        except Exception as e:
            logger.warning(f"Could not set permissions/ownership for {user_home_path}: {str(e)}")
            # This is not critical, so we continue
        
        return True
        
    except Exception as e:
        logger.error(f"Error creating user home directory: {str(e)}")
        return False


def verify_user_home_path(username):
    """
    Verify that a user's home directory exists and contains all the expected content.
    If it doesn't exist or is missing content, recreate it.
    
    Args:
        username (str): Username to verify directory for
        
    Returns:
        dict: Status information about the user's home directory
    """
    try:
        user_home_path = os.path.join('/home', username)
        template_dir = '/template' if os.path.exists('/template') else '/app/template'
        
        # Status dictionary to return
        status = {
            "username": username,
            "home_path": user_home_path,
            "exists": os.path.exists(user_home_path),
            "template_path": template_dir,
            "template_exists": os.path.exists(template_dir),
        }
        
        # If the home directory doesn't exist, create it
        if not os.path.exists(user_home_path):
            logger.info(f"User home directory does not exist, creating: {user_home_path}")
            success = create_user_home_path(username, template_dir)
            status["created"] = success
            
            # If creation was successful, update status
            if success:
                status["exists"] = True
                status["files"] = os.listdir(user_home_path)
        else:
            # If it exists, check if it has the expected content
            status["files"] = os.listdir(user_home_path)
            
            # If template exists, check if all expected files are present
            if os.path.exists(template_dir):
                template_files = os.listdir(template_dir)
                status["template_files"] = template_files
                
                # Check for missing files
                missing_files = [f for f in template_files if f not in status["files"]]
                status["missing_files"] = missing_files
                
                # If files are missing, copy them
                if missing_files:
                    logger.info(f"User home directory missing files: {missing_files}")
                    for item in missing_files:
                        source = os.path.join(template_dir, item)
                        destination = os.path.join(user_home_path, item)
                        
                        if os.path.isdir(source):
                            shutil.copytree(source, destination)
                            logger.info(f"Copied missing directory: {source} -> {destination}")
                        else:
                            shutil.copy2(source, destination)
                            logger.info(f"Copied missing file: {source} -> {destination}")
                    
                    # Update file list after copying
                    status["files"] = os.listdir(user_home_path)
                    status["updated"] = True
        
        return status
    
    except Exception as e:
        logger.error(f"Error verifying user home directory: {str(e)}")
        return {
            "username": username,
            "error": str(e),
            "success": False
        }