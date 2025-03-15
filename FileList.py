import os
import platform
import getpass
import htmlGenerator
from flask import render_template
from markupsafe import Markup


def file_list(osfolder, path, original_path=None):
    """
    List files in the given path
    
    Args:
        osfolder: OS-specific folder prefix
        path: The physical path on the current system
        original_path: The original path in the URL (for keeping URL structure consistent)
    """
    # Get the home directory based on the OS using utility function
    import utils
    home_path = utils.get_home_directory()
    # If original_path is not provided, use path
    if original_path is None:
        original_path = path
        
    try:
        list_of_files = os.listdir(osfolder + path)
        list_of_files.sort()
        collect_files = ''
        
        # Get available species for reference
        available_species = htmlGenerator.available_species()
        
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
        
        # Handle special case for user folders without species subfolders
        path_parts = original_path.strip('/').split('/')
        
        # Path structure should be: home/username/speciesname/project
        if len(path_parts) >= 2 and path_parts[0] == "home":
            username = path_parts[1] if len(path_parts) > 1 else ""
            
            # If we're just in a user folder (/home/username/) with no species subfolder
            if len(path_parts) == 2:
                collect_files += f'<li><b>User directory: {username}</b></li>'
                collect_files += '<li>Please select or create a species folder within this directory.</li>'
                collect_files += '<li>BattyCoda requires folders organized by bat species containing the call data.</li>'
                
                # Show available species for this user path - only for user's own directory
                if available_species and (username == getpass.getuser() or username.lower() == "shared"):
                    collect_files += '<li><b>Available species templates:</b></li>'
                    for species in available_species:
                        # For non-existent folders, only link to info and show a message
                        species_path = f"{osfolder}{home_path}/{username}/{species}"
                        if os.path.isdir(species_path):
                            # The species folder exists, make it clickable
                            collect_files += f'<li><a href="/battycoda/home/{username}/{species}/">{species}</a> [<a href="/species_info/{species}">Info</a>]</li>'
                        else:
                            # Only show info link for non-existent folders
                            collect_files += f'<li>{species} (not created yet) [<a href="/species_info/{species}">Info</a>]</li>'
                else:
                    collect_files += '<li>No species templates available. Please make sure data files are correctly installed in the static folder.</li>'
                
                # Return early with this specialized message
                return render_template('listBC.html', data={'listicle': Markup(collect_files)})
            
            # If we're in a specific species folder but it's not a recognized species
            if len(path_parts) >= 3:
                species_name = path_parts[2] 
                if species_name not in available_species:
                    collect_files += f'<li><b>Species folder "{species_name}" is not recognized.</b></li>'
                    collect_files += '<li>BattyCoda requires specific bat species data and templates.</li>'
                    
                    # Show available alternative species for this user
                    if available_species:
                        collect_files += '<li><b>Available species templates:</b></li>'
                        for species in available_species:
                            # For non-existent folders, only link to info and show a message
                            species_path = f"{osfolder}{home_path}/{username}/{species}"
                            if os.path.isdir(species_path):
                                # The species folder exists, make it clickable
                                collect_files += f'<li><a href="/battycoda/home/{username}/{species}/">{species}</a> [<a href="/species_info/{species}">Info</a>]</li>'
                            else:
                                # Only show info link for non-existent folders
                                collect_files += f'<li>{species} (not created yet) [<a href="/species_info/{species}">Info</a>]</li>'
                    else:
                        collect_files += '<li>No species templates available. Please make sure data files are correctly installed in the static folder.</li>'
                    
                    # Return early with this specialized message
                    return render_template('listBC.html', data={'listicle': Markup(collect_files)})
        
        # Process regular directory listing
        for item in list_of_files:
            # Skip dotfiles and dotfolders
            if item.startswith('.'):
                continue
                
            # Check if we're in the home directory equivalent
            is_home_dir = path.endswith('home/') or path.endswith('Users/')
            
            if is_home_dir and item.endswith('lost+found'):
                continue
            if is_home_dir and item.endswith('data'):
                continue
                
            # Use original URL path structure for consistent path handling
            item_path = original_path + item
            path_parts = original_path.strip('/').split('/')
            
            # Skip filtering in home root or username directories
            if original_path == "home/" or (len(path_parts) == 2 and path_parts[0] == "home"):
                pass
            # For species directories (home/username/species), check if recognized
            elif len(path_parts) == 3 and path_parts[0] == "home":
                species_name = path_parts[2]
                if species_name not in available_species:
                    # Don't filter at this level - we want to show all folders
                    pass
                
            # Check if it's a directory
            if os.path.isdir(osfolder + path + item):
                collect_files += '<li><a href="' + item + '/">' + item + '</a> (folder)</li>'
            # Check for WAV files with paired pickle files
            elif item.lower().endswith('.wav') and os.path.isfile(osfolder + path + item + '.pickle'):
                collect_files += '<li><a href="' + item + '/">' + item + '</a> <span style="color: green;">(clickable: has paired pickle file with call data)</span></li>'
            # Check for WAV files without paired pickle files
            elif item.lower().endswith('.wav'):
                collect_files += '<li>' + item + ' <span style="color: #888;">(not clickable: missing paired pickle file)</span></li>'
            # Check for pickle files with paired wav files
            elif item.lower().endswith('.pickle'):
                if item.lower().endswith('.wav.pickle'):
                    # This is a pickle file for a wav file
                    wav_file = item[:-7]  # Remove .pickle from the end
                    if os.path.isfile(osfolder + path + wav_file):
                        collect_files += '<li>' + item + ' <span style="color: #0066cc;">(pickle file that defines call starts, stops, and labels for the WAV file)</span></li>'
                    else:
                        collect_files += '<li>' + item + ' <span style="color: #888;">(pickle file missing its paired WAV file)</span></li>'
                else:
                    # Other pickle files
                    collect_files += '<li>' + item + ' <span style="color: #888;">(pickle file)</span></li>'
            # Any other files
            else:
                collect_files += '<li>' + item + '</li>'
        
        # If no files were found after filtering, show helpful message based on path level
        if not collect_files:
            path_parts = original_path.strip('/').split('/')
            
            if original_path == "home/":
                # Root home directory
                collect_files += '<li><b>No user directories found.</b></li>'
                collect_files += '<li>Please create a user directory structure: /home/username/species/project</li>'
            elif len(path_parts) == 2 and path_parts[0] == "home":
                # User directory
                username = path_parts[1]
                collect_files += f'<li><b>No species folders found in user directory: {username}.</b></li>'
                collect_files += '<li>Please create species folders within this directory.</li>'
                
                # Show available species templates
                if available_species:
                    collect_files += '<li><b>Available species templates:</b></li>'
                    for species in available_species:
                        # For non-existent folders, only link to info and show a message
                        species_path = f"{osfolder}{home_path}/{username}/{species}"
                        if os.path.isdir(species_path):
                            # The species folder exists, make it clickable
                            collect_files += f'<li><a href="/battycoda/home/{username}/{species}/">{species}</a> [<a href="/species_info/{species}">Info</a>]</li>'
                        else:
                            # Only show info link for non-existent folders
                            collect_files += f'<li>{species} (not created yet) [<a href="/species_info/{species}">Info</a>]</li>'
            elif len(path_parts) >= 3 and path_parts[0] == "home":
                # Species or project directory
                username = path_parts[1]
                species = path_parts[2]
                
                collect_files += f'<li><b>No data found in species folder: {species}.</b></li>'
                collect_files += '<li>Please make sure this folder contains bat call data files.</li>'
                
                # Show navigation options
                collect_files += f'<li><a href="/battycoda/home/{username}/">Return to user directory</a></li>'
            else:
                # Generic empty directory
                collect_files += '<li><b>No data found in this directory.</b></li>'

        return render_template('listBC.html', data={'listicle': Markup(collect_files)})

    except PermissionError:
        # Handle permission error by showing a placeholder message
        collect_files = '<li>Permission error accessing this directory</li>'
        return render_template('listBC.html', data={'listicle': Markup(collect_files)})
        
    except FileNotFoundError:
        # Check path structure
        try:
            path_parts = original_path.strip('/').split('/')
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
                    message += f'<li><a href="/battycoda/home/{current_user}/">Go to your user directory ({current_user})</a></li>'
                    
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
                            message += f'<li><a href="/battycoda/home/{user}/">{user}</a></li>'
                    
                elif len(path_parts) >= 3:
                    # Species or project directory
                    species_name = path_parts[2]
                    
                    message = f'<li><b>Directory not found: {species_name}</b></li>'
                    
                    if species_name in available:
                        message += '<li>This species template exists, but the folder has not been created.</li>'
                        home_directory = utils.get_home_directory()
                        message += f'<li>You need to create the folder: <code>/{home_directory}/{username}/{species_name}</code></li>'
                    else:
                        message += '<li>This is not a recognized species template.</li>'
                    
                    # Show available species
                    if available:
                        message += '<li><b>Available species templates:</b></li>'
                        for species in available:
                            message += f'<li><a href="/battycoda/home/{username}/{species}/">{species}</a> [<a href="/species_info/{species}">Info</a>]</li>'
                
                return render_template('listBC.html', data={'listicle': Markup(message)})
            
            # Generic directory not found
            collect_files = '<li>Directory not found</li>'
            return render_template('listBC.html', data={'listicle': Markup(collect_files)})
            
        except Exception as e:
            # Handle any errors in the error handler
            message = f'<li><b>Error handling path: {str(e)}</b></li>'
            message += '<li><a href="/">Return to home page</a></li>'
            return render_template('listBC.html', data={'listicle': Markup(message)})
            
    except Exception as e:
        # Handle any unexpected errors
        message = f'<li><b>Unexpected error: {str(e)}</b></li>'
        message += '<li><a href="/">Return to home page</a></li>'
        return render_template('listBC.html', data={'listicle': Markup(message)})