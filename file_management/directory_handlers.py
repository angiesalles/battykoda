"""
Directory handlers for FileList module.
"""
import os
import platform
import getpass
import logging
from flask import render_template
from markupsafe import Markup

import htmlGenerator
import utils

# Set up logging
logger = logging.getLogger('battykoda.directory_handlers')

def list_users_directory(path: str) -> str:
    """
    List the top-level users directory (/home/)
    
    Args:
        path: Path to the users directory (home/)
        
    Returns:
        str: Rendered HTML with users directory listing
    """
    import utils
    
    # Convert path once at the beginning
    os_specific_path = utils.convert_path_to_os_specific(path)
    logger.info(f"Listing users directory: {path} -> {os_specific_path}")
    
    try:
        # Get directory contents
        list_of_files = os.listdir(os_specific_path)
        list_of_files.sort()
        
        # Filter out system files and hidden files
        list_of_files = [f for f in list_of_files if not f.startswith('.')]
        
        collect_files = '<h2>User Directories</h2>'
        collect_files += '<p>Select a user directory to proceed:</p>'
        
        # List each user directory with a link
        for item in list_of_files:
            full_path = os.path.join(os_specific_path, item)
            if os.path.isdir(full_path):
                collect_files += f'<li><a href="{item}/">{item}</a> (user directory)</li>'
        
        # If no users found
        if not any(os.path.isdir(os.path.join(os_specific_path, item)) for item in list_of_files):
            collect_files += '<li><b>No user directories found.</b></li>'
            collect_files += '<li>Please create a user directory structure: /home/username/species/project</li>'
            
            # Add current user option
            current_user = getpass.getuser()
            collect_files += f'<li><a href="{current_user}/">Create directory for current user ({current_user})</a></li>'
        
        return render_template('listBC.html', data={'listicle': Markup(collect_files)})
        
    except Exception as e:
        logger.error(f"Error in list_users_directory: {str(e)}")
        raise


def list_species_directory(path: str, username: str) -> str:
    """
    List the species directories within a user directory (/home/username/)
    
    Args:
        path: Path to the user's directory (home/username/)
        username: Username of the directory owner
        
    Returns:
        str: Rendered HTML with species directory listing
    """
    import utils
    
    # Convert path once at the beginning
    os_specific_path = utils.convert_path_to_os_specific(path)
    logger.info(f"Listing species directory: {path} -> {os_specific_path}")
    
    try:
        # Get directory contents
        list_of_files = os.listdir(os_specific_path)
        list_of_files.sort()
        
        # Get available species templates for reference
        available_species = htmlGenerator.available_species()
        
        collect_files = f'<h2>Species Directories for User: {username}</h2>'
        collect_files += '<p>Select a species directory:</p>'
        
        # List each species directory with a link
        for item in list_of_files:
            # Skip hidden files
            if item.startswith('.'):
                continue
                
            full_path = os.path.join(os_specific_path, item)
            if os.path.isdir(full_path):
                is_recognized = item in available_species
                if is_recognized:
                    # Recognized species - make clickable with green label
                    collect_files += f'<li><a href="{item}/">{item}</a> <span style="color: green;">(recognized species)</span></li>'
                else:
                    # Non-recognized species - not clickable
                    collect_files += f'<li>{item} <span style="color: #888;">(unrecognized species)</span></li>'
        
        # If no species directories found
        if not any(os.path.isdir(os.path.join(os_specific_path, item)) 
                  and not item.startswith('.') for item in list_of_files):
            collect_files += f'<li><b>No species folders found in user directory: {username}.</b></li>'
            collect_files += '<li>Please create species folders within this directory.</li>'
            
            # Show available species templates
            if available_species:
                collect_files += '<li><b>Available species templates:</b></li>'
                for species in available_species:
                    collect_files += f'<li><a href="{species}/">{species}</a> [<a href="/species_info/{species}">Info</a>]</li>'
        
        return render_template('listBC.html', data={'listicle': Markup(collect_files)})
        
    except Exception as e:
        logger.error(f"Error in list_species_directory: {str(e)}")
        raise


def list_project_directory(path: str, username: str, species: str) -> str:
    """
    List the contents of a project directory or any directory containing WAV files
    (/home/username/species/... and deeper)
    
    Args:
        path: Path to the project directory
        username: Username of the directory owner
        species: Species name
        
    Returns:
        str: Rendered HTML with project directory listing
    """
    import utils
    
    # Convert path once at the beginning
    os_specific_path = utils.convert_path_to_os_specific(path)
    logger.info(f"Listing project directory: {path} -> {os_specific_path}")
    
    try:
        # Get directory contents
        list_of_files = os.listdir(os_specific_path)
        list_of_files.sort()
        
        # Check available species for reference
        available_species = htmlGenerator.available_species()
        is_recognized_species = species in available_species
        
        collect_files = f'<h2>Project Directory: {os.path.basename(os_specific_path)}</h2>'
        if not is_recognized_species:
            collect_files += f'<div style="background-color: #fff3cd; padding: 10px; border-left: 5px solid #ffc107; margin-bottom: 15px;">'
            collect_files += f'<p><strong>Warning:</strong> Species folder "{species}" is not a recognized species template.</p>'
            collect_files += '</div>'
        
        # Check if this directory contains WAV files
        has_wav_files = any(item.lower().endswith('.wav') for item in list_of_files)
        if has_wav_files:
            collect_files += '<div style="margin: 10px 0; padding: 15px; background-color: #1e1e1e; border-left: 4px solid #3498db; border-radius: 5px;">'
            collect_files += '<h3 style="color: #e57373; margin-top: 0;">WAV File Guide:</h3>'
            collect_files += '<ul style="color: white; margin-bottom: 0;">'
            collect_files += '<li><strong style="color: #4CAF50;">Green</strong> items are clickable WAV files with paired pickle files containing call data.</li>'
            collect_files += '<li>Pickle files contain the call starts, stops, and labels for the WAV files.</li>'
            collect_files += '<li>To make a WAV file clickable, it needs a matching pickle file (filename.wav.pickle).</li>'
            collect_files += '</ul>'
            collect_files += '</div>'
        
        # Process files and subdirectories
        for item in list_of_files:
            # Skip hidden files
            if item.startswith('.'):
                continue
                
            full_path = os.path.join(os_specific_path, item)
            
            # Determine item type and format accordingly
            if os.path.isdir(full_path):
                collect_files += '<li><a href="' + item + '/">' + item + '</a> (folder)</li>'
            elif item.lower().endswith('.wav') and os.path.isfile(full_path + '.pickle'):
                collect_files += '<li><a href="' + item + '">' + item + '</a> <span style="color: green;">(clickable: has paired pickle file with call data)</span></li>'
            elif item.lower().endswith('.wav'):
                collect_files += '<li>' + item + ' <span style="color: #888;">(not clickable: missing paired pickle file)</span></li>'
            elif item.lower().endswith('.pickle'):
                if item.lower().endswith('.wav.pickle'):
                    # This is a pickle file for a wav file
                    wav_file = item[:-7]  # Remove .pickle from the end
                    wav_path = os.path.join(os_specific_path, wav_file)
                    if os.path.isfile(wav_path):
                        collect_files += '<li>' + item + ' <span style="color: #0066cc;">(pickle file that defines call starts, stops, and labels for the WAV file)</span></li>'
                    else:
                        collect_files += '<li>' + item + ' <span style="color: #888;">(pickle file missing its paired WAV file)</span></li>'
                else:
                    # Other pickle files
                    collect_files += '<li>' + item + ' <span style="color: #888;">(pickle file)</span></li>'
            else:
                collect_files += '<li>' + item + '</li>'
        
        # If no files were found after filtering
        if not any(not item.startswith('.') for item in list_of_files):
            collect_files += f'<li><b>No data found in this directory.</b></li>'
            collect_files += '<li>Please add WAV files and their corresponding pickle files.</li>'
            
            # Add navigation links
            collect_files += f'<li><a href="/home/{username}/">Return to user directory</a></li>'
        
        return render_template('listBC.html', data={'listicle': Markup(collect_files)})
        
    except Exception as e:
        logger.error(f"Error in list_project_directory: {str(e)}")
        raise


def handle_file_not_found_error(path: str) -> str:
    """
    Handle FileNotFoundError by providing helpful messages based on path structure
    
    Args:
        path: The path that wasn't found
        
    Returns:
        str: Rendered HTML with appropriate error message
    """
    import utils
    
    try:
        path_parts = path.strip('/').split('/')
        available = htmlGenerator.available_species()
        
        if len(path_parts) >= 1 and path_parts[0] == "home":
            # Get username if present in path
            username = path_parts[1] if len(path_parts) > 1 else ""
            
            if len(path_parts) == 1:
                # Just /home/ path
                message = '<li><b>Home directory not found.</b></li>'
                message += '<li>Please make sure your user directory exists.</li>'
                
                # Get current username
                current_user = getpass.getuser()
                message += f'<li><a href="/home/{current_user}/">Go to your user directory ({current_user})</a></li>'
                
            elif len(path_parts) == 2:
                # User directory path
                message = f'<li><b>User directory not found: {username}</b></li>'
                message += '<li>This directory does not exist on your system.</li>'
                
                # List available user directories
                message += '<li><b>Available user directories:</b></li>'
                
                # Use utility functions to get user directories
                user_dir = f"/{utils.get_home_directory()}"
                users = os.listdir(user_dir)
                # Filter out system directories and dotfiles
                users = [u for u in users if not u.startswith('.') and u != 'Shared']
                users.sort()
                
                for user in users:
                    if os.path.isdir(os.path.join(user_dir, user)):
                        message += f'<li><a href="/home/{user}/">{user}</a></li>'

            elif len(path_parts) >= 3:
                # Species or project directory
                species_name = path_parts[2]

                message = f'<li><b>Directory not found: {species_name}</b></li>'
                
                if species_name in available:
                    message += '<li>This species template exists, but the folder has not been created.</li>'
                    home_directory = utils.get_home_directory()
                else:
                    message += '<li>This is not a recognized species template.</li>'
                
                # Show available species
                if available:
                    message += '<li><b>Available species templates:</b></li>'
                    for species in available:
                        message += f'<li><a href="/home/{username}/{species}/">{species}</a> [<a href="/species_info/{species}">Info</a>]</li>'
            
            return render_template('listBC.html', data={'listicle': Markup(message)})
        
        # Generic directory not found
        message = '<li>Directory not found</li>'
        return render_template('listBC.html', data={'listicle': Markup(message)})
        
    except Exception as e:
        # Handle any errors in the error handler
        logger.error(f"Error in handle_file_not_found_error: {str(e)}")
        message = f'<li><b>Error handling path: {str(e)}</b></li>'
        message += '<li><a href="/">Return to home page</a></li>'
        return render_template('listBC.html', data={'listicle': Markup(message)})