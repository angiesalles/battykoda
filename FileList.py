import os
import platform
import htmlGenerator
from flask import render_template
from markupsafe import Markup
import getpass


def file_list(osfolder, path, original_path=None):
    """
    List files in the given path
    
    Args:
        osfolder: OS-specific folder prefix
        path: The physical path on the current system
        original_path: The original path in the URL (for keeping URL structure consistent)
    """
    # If original_path is not provided, use path
    if original_path is None:
        original_path = path
        
    try:
        list_of_files = os.listdir(osfolder + path)
        list_of_files.sort()
        collect_files = ''
        
        # Get available species for reference
        available_species = htmlGenerator.available_species()
        
        # Handle special case for user folders without species subfolders
        path_parts = original_path.strip('/').split('/')
        
        # Path structure should be: home/username/speciesname/project
        if len(path_parts) >= 2 and path_parts[0] == "home":
            username = path_parts[1] if len(path_parts) > 1 else ""
            
            # If we're just in a user folder (/home/username/) with no species subfolder
            if len(path_parts) == 2:
                collect_files += f'<li><b>User directory: {username}</b></li>'
                collect_files += '<li>Please select or create a species folder within this directory.</li>'
                collect_files += '<li>BattyKoda requires folders organized by bat species containing the call data.</li>'
                
                # Show available species for this user path
                if available_species:
                    collect_files += '<li><b>Available species templates:</b></li>'
                    for species in available_species:
                        collect_files += f'<li><a href="/battykoda/home/{username}/{species}/">{species}</a></li>'
                else:
                    collect_files += '<li>No species templates available. Please make sure data files are correctly installed in the static folder.</li>'
                
                # Return early with this specialized message
                return render_template('listBK.html', data={'listicle': Markup(collect_files)})
            
            # If we're in a specific species folder but it's not a recognized species
            if len(path_parts) >= 3:
                species_name = path_parts[2] 
                if species_name not in available_species:
                    collect_files += f'<li><b>Species folder "{species_name}" is not recognized.</b></li>'
                    collect_files += '<li>BattyKoda requires specific bat species data and templates.</li>'
                    
                    # Show available alternative species for this user
                    if available_species:
                        collect_files += '<li><b>Available species templates:</b></li>'
                        for species in available_species:
                            collect_files += f'<li><a href="/battykoda/home/{username}/{species}/">{species}</a></li>'
                    else:
                        collect_files += '<li>No species templates available. Please make sure data files are correctly installed in the static folder.</li>'
                    
                    # Return early with this specialized message
                    return render_template('listBK.html', data={'listicle': Markup(collect_files)})
        
        # Process regular directory listing
        for item in list_of_files:
            if '.git' in item:
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
                
            if os.path.isdir(osfolder + path + item) or os.path.isfile(osfolder + path + item+'.pickle'):
                collect_files += '<li><a href="' + item + '/">' + item + '</a></li>'
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
                        collect_files += f'<li><a href="/battykoda/home/{username}/{species}/">{species}</a></li>'
            elif len(path_parts) >= 3 and path_parts[0] == "home":
                # Species or project directory
                username = path_parts[1]
                species = path_parts[2]
                
                collect_files += f'<li><b>No data found in species folder: {species}.</b></li>'
                collect_files += '<li>Please make sure this folder contains bat call data files.</li>'
                
                # Show navigation options
                collect_files += f'<li><a href="/battykoda/home/{username}/">Return to user directory</a></li>'
            else:
                # Generic empty directory
                collect_files += '<li><b>No data found in this directory.</b></li>'

        return render_template('listBK.html', data={'listicle': Markup(collect_files)})

    except PermissionError:
        # Handle permission error by showing a placeholder message
        collect_files = '<li>Permission error accessing this directory</li>'
        return render_template('listBK.html', data={'listicle': Markup(collect_files)})
        
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
                    message += f'<li><a href="/battykoda/home/{current_user}/">Go to your user directory ({current_user})</a></li>'
                    
                elif len(path_parts) == 2:
                    # User directory path
                    message = f'<li><b>User directory not found: {username}</b></li>'
                    message += '<li>This directory does not exist on your system.</li>'
                    
                    # List available user directories
                    message += '<li><b>Available user directories:</b></li>'
                    
                    if platform.system() == "Darwin":  # macOS
                        user_dir = "/Users"
                        users = os.listdir(user_dir)
                        # Filter out system directories
                        users = [u for u in users if not u.startswith('.') and u != 'Shared']
                        users.sort()
                        
                        for user in users:
                            if os.path.isdir(os.path.join(user_dir, user)):
                                message += f'<li><a href="/battykoda/home/{user}/">{user}</a></li>'
                    
                elif len(path_parts) >= 3:
                    # Species or project directory
                    species_name = path_parts[2]
                    
                    message = f'<li><b>Directory not found: {species_name}</b></li>'
                    
                    if species_name in available:
                        message += '<li>This species template exists, but the folder has not been created.</li>'
                        message += f'<li>You need to create the folder: <code>/Users/{username}/{species_name}</code></li>'
                    else:
                        message += '<li>This is not a recognized species template.</li>'
                    
                    # Show available species
                    if available:
                        message += '<li><b>Available species templates:</b></li>'
                        for species in available:
                            message += f'<li><a href="/battykoda/home/{username}/{species}/">{species}</a></li>'
                
                return render_template('listBK.html', data={'listicle': Markup(message)})
            
            # Generic directory not found
            collect_files = '<li>Directory not found</li>'
            return render_template('listBK.html', data={'listicle': Markup(collect_files)})
            
        except Exception as e:
            # Handle any errors in the error handler
            message = f'<li><b>Error handling path: {str(e)}</b></li>'
            message += '<li><a href="/">Return to home page</a></li>'
            return render_template('listBK.html', data={'listicle': Markup(message)})
            
    except Exception as e:
        # Handle any unexpected errors
        message = f'<li><b>Unexpected error: {str(e)}</b></li>'
        message += '<li><a href="/">Return to home page</a></li>'
        return render_template('listBK.html', data={'listicle': Markup(message)})