"""
Main file listing module for BattyCoda application.
This module provides the main file listing functionality.
"""
import os
import logging
from flask import render_template
from markupsafe import Markup
from typing import Final

# Import directory handlers
from file_management.directory_handlers import (
    list_users_directory,
    list_species_directory,
    list_project_directory,
    handle_file_not_found_error
)

# Set up logging
logger = logging.getLogger('battykoda.filelist')

def file_list(path: Final[str]) -> str:
    """
    List files in the given path - main dispatcher function based on path level
    
    Args:
        path: The physical path on the current system - treated as constant
              
    Returns:
        str: HTML rendered content listing files in the path
    """
    import utils
    
    # Path structure analysis
    path_parts = path.strip('/').split('/')
    
    try:
        # Determine path type and call the appropriate specialized function
        if path_parts[0] == "home":
            if len(path_parts) == 1:  # /home/ - Users directory
                return list_users_directory(path)
            elif len(path_parts) == 2:  # /home/username/ - Species directory
                return list_species_directory(path, path_parts[1])
            else:  # /home/username/species/... - Project or WAV files directory
                return list_project_directory(path, path_parts[1], path_parts[2])
        else:
            # Handle unknown path structure
            logger.warning(f"Unknown path structure: {path}")
            return render_template('listBC.html', 
                                  data={'listicle': Markup('<li><b>Unknown path structure</b></li>')})
    except FileNotFoundError:
        # Directory doesn't exist
        return handle_file_not_found_error(path)
    except PermissionError:
        # Permission error
        return render_template('listBC.html', 
                             data={'listicle': Markup('<li>Permission error accessing this directory</li>')})
    except Exception as e:
        # Handle any unexpected errors
        logger.error(f"Unexpected error in file_list: {str(e)}")
        message = f'<li><b>Unexpected error: {str(e)}</b></li>'
        message += '<li><a href="/">Return to home page</a></li>'
        return render_template('listBC.html', data={'listicle': Markup(message)})