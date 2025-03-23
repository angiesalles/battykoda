"""
Directory handlers for the BattyCoda application.
"""
import getpass
import logging
import os

from django.shortcuts import redirect, render
from django.utils.safestring import mark_safe

from .utils import available_species, convert_path_to_os_specific, ensure_user_directory_exists, get_home_directory

# Set up logging
logger = logging.getLogger("battycoda.directory_handlers")


def generate_create_directory_form(path):
    """
    Generate an HTML form for creating a new directory

    Args:
        path (str): The current path where the directory will be created

    Returns:
        str: HTML form for directory creation
    """
    return f"""
    <div style="margin: 20px 0; background-color: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 4px solid #2ecc71;">
        <h3 style="margin-top: 0; color: #2c3e50;">Create New Directory</h3>
        <form action="/create-directory/" method="POST" style="display: flex; flex-wrap: wrap; gap: 10px; align-items: flex-end;">
            <input type="hidden" name="csrfmiddlewaretoken" value="">
            <input type="hidden" name="path" value="{path}">
            <div>
                <label for="directory_name" style="display: block; margin-bottom: 5px; font-weight: bold;">Directory Name:</label>
                <input type="text" name="directory_name" id="directory_name" required 
                       style="padding: 8px; border: 1px solid #ddd; border-radius: 4px; width: 200px;">
            </div>
            <button type="submit" class="button" style="background-color: #2ecc71; color: white; border: none; padding: 8px 15px; border-radius: 4px; cursor: pointer;">
                Create Directory
            </button>
        </form>
    </div>
    """


def generate_file_upload_form(path):
    """
    Generate an HTML form for uploading files with real-time progress tracking

    Args:
        path (str): The current path where the file will be uploaded

    Returns:
        str: HTML form for file upload with real progress tracking
    """
    return f"""
    <div style="margin: 20px 0; background-color: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 4px solid #3498db;">
        <h3 style="margin-top: 0; color: #2c3e50;">Upload File</h3>
        
        <div id="upload-container-{path.replace('/', '-')}">
            <div style="display: flex; flex-wrap: wrap; gap: 10px; align-items: flex-end;">
                <div>
                    <label for="file-{path.replace('/', '-')}" style="display: block; margin-bottom: 5px; font-weight: bold;">Select File:</label>
                    <div style="position: relative; overflow: hidden;">
                        <button type="button" style="background-color: white; color: #333; border: 1px solid #ddd; padding: 8px 15px; border-radius: 4px; cursor: pointer; display: inline-block; margin-right: 10px;">
                            Browse...
                        </button>
                        <span id="file-name-display-{path.replace('/', '-')}" style="color: #333; font-size: 0.9em;">No file selected</span>
                        <input type="file" name="file" id="file-{path.replace('/', '-')}" required 
                               style="position: absolute; top: 0; left: 0; opacity: 0; width: 100%; height: 100%; cursor: pointer;"
                               onchange="document.getElementById('file-name-display-{path.replace('/', '-')}').textContent = this.files[0] ? this.files[0].name : 'No file selected'; document.getElementById('progress-container-{path.replace('/', '-')}').style.display = 'none';">
                    </div>
                </div>
                <button type="button" id="upload-button-{path.replace('/', '-')}" class="button" style="background-color: #3498db; color: white; border: none; padding: 8px 15px; border-radius: 4px; cursor: pointer;">
                    Upload File
                </button>
            </div>
            <div id="progress-container-{path.replace('/', '-')}" style="display: none; width: 100%; margin-top: 10px;">
                <div style="background-color: #f1f1f1; border-radius: 4px; padding: 3px; width: 100%;">
                    <div id="progress-bar-{path.replace('/', '-')}" style="background-color: #4CAF50; height: 20px; border-radius: 2px; width: 0%; text-align: center; line-height: 20px; color: white;">0%</div>
                </div>
                <div id="upload-status-{path.replace('/', '-')}" style="font-size: 0.9em; margin-top: 5px; color: #333;">Preparing upload...</div>
            </div>
        </div>
        
        <script>
            (function() {{
                // Get elements
                var fileInput = document.getElementById('file-{path.replace('/', '-')}');
                var uploadButton = document.getElementById('upload-button-{path.replace('/', '-')}');
                var progressContainer = document.getElementById('progress-container-{path.replace('/', '-')}');
                var progressBar = document.getElementById('progress-bar-{path.replace('/', '-')}');
                var uploadStatus = document.getElementById('upload-status-{path.replace('/', '-')}');
                
                // Upload button click handler
                uploadButton.addEventListener('click', function() {{
                    // Check if a file is selected
                    if (fileInput.files.length === 0) {{
                        alert('Please select a file to upload.');
                        return;
                    }}
                    
                    var file = fileInput.files[0];
                    
                    // Check file size (limit to 2GB for safety)
                    var maxSize = 2 * 1024 * 1024 * 1024; // 2GB in bytes
                    if (file.size > maxSize) {{
                        alert('File is too large. Maximum file size is 2GB.');
                        return;
                    }}
                    
                    // Setup FormData
                    var formData = new FormData();
                    formData.append('file', file);
                    formData.append('path', '{path}');
                    
                    // Get CSRF token from cookie
                    function getCookie(name) {{
                        let cookieValue = null;
                        if (document.cookie && document.cookie !== '') {{
                            const cookies = document.cookie.split(';');
                            for (let i = 0; i < cookies.length; i++) {{
                                const cookie = cookies[i].trim();
                                if (cookie.substring(0, name.length + 1) === (name + '=')) {{
                                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                                    break;
                                }}
                            }}
                        }}
                        return cookieValue;
                    }}
                    var csrfToken = getCookie('csrftoken');
                    
                    // Create and configure XMLHttpRequest
                    var xhr = new XMLHttpRequest();
                    
                    // Show progress container
                    progressContainer.style.display = 'block';
                    
                    // Handle progress events
                    xhr.upload.addEventListener('progress', function(e) {{
                        if (e.lengthComputable) {{
                            var percentComplete = (e.loaded / e.total) * 100;
                            
                            // Update the progress bar
                            progressBar.style.width = percentComplete + '%';
                            progressBar.textContent = Math.floor(percentComplete) + '%';
                            
                            // Update status with file size info
                            var totalSize = formatBytes(e.total);
                            var loadedSize = formatBytes(e.loaded);
                            uploadStatus.textContent = 'Uploading... ' + loadedSize + ' of ' + totalSize;
                        }}
                    }});
                    
                    // Handle completion
                    xhr.addEventListener('load', function() {{
                        if (xhr.status === 200) {{
                            // Parse the response
                            try {{
                                var response = JSON.parse(xhr.responseText);
                                // Upload complete
                                progressBar.style.width = '100%';
                                progressBar.textContent = '100%';
                                uploadStatus.textContent = 'Upload complete! File: ' + response.file_name + ' uploaded successfully. Refreshing...';
                                
                                // Refresh the page after a short delay
                                setTimeout(function() {{
                                    window.location.reload();
                                }}, 1000);
                            }} catch (e) {{
                                console.error('Error parsing response:', e);
                                // Show a success message anyway since status was 200
                                progressBar.style.width = '100%';
                                progressBar.textContent = '100%';
                                uploadStatus.textContent = 'Upload complete! Refreshing in 2 seconds...';
                                
                                // Refresh the page after a short delay
                                setTimeout(function() {{
                                    window.location.reload();
                                }}, 2000);
                            }}
                        }} else {{
                            // Error occurred
                            progressBar.style.backgroundColor = '#e74c3c';
                            uploadStatus.textContent = 'Error uploading file: ' + xhr.statusText;
                            
                            // Re-enable the upload button
                            uploadButton.disabled = false;
                            uploadButton.textContent = 'Upload File';
                            uploadButton.style.backgroundColor = '#3498db';
                        }}
                    }});
                    
                    // Handle network errors
                    xhr.addEventListener('error', function() {{
                        progressBar.style.backgroundColor = '#e74c3c';
                        uploadStatus.textContent = 'Network error during upload. Please try again.';
                        console.error('Network error during upload:', xhr);
                        
                        // Re-enable the upload button
                        uploadButton.disabled = false;
                        uploadButton.textContent = 'Upload File';
                        uploadButton.style.backgroundColor = '#3498db';
                    }});
                    
                    // Add timeout handler for long requests
                    xhr.timeout = 300000; // 5 minutes timeout
                    xhr.ontimeout = function() {{
                        progressBar.style.backgroundColor = '#e74c3c';
                        uploadStatus.textContent = 'Upload timed out after 5 minutes. The file may be too large or the server is busy.';
                        console.error('Upload timed out');
                        
                        // Re-enable the upload button
                        uploadButton.disabled = false;
                        uploadButton.textContent = 'Upload File';
                        uploadButton.style.backgroundColor = '#3498db';
                    }};
                    
                    // Handle aborted uploads
                    xhr.addEventListener('abort', function() {{
                        progressBar.style.backgroundColor = '#e74c3c';
                        uploadStatus.textContent = 'Upload cancelled.';
                        
                        // Re-enable the upload button
                        uploadButton.disabled = false;
                        uploadButton.textContent = 'Upload File';
                        uploadButton.style.backgroundColor = '#3498db';
                    }});
                    
                    // Disable the upload button
                    uploadButton.disabled = true;
                    uploadButton.textContent = 'Uploading...';
                    uploadButton.style.backgroundColor = '#95a5a6';
                    
                    // Send the upload with CSRF token
                    xhr.open('POST', '/upload-file/', true);
                    xhr.setRequestHeader('X-CSRFToken', csrfToken);
                    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
                    xhr.send(formData);
                }});
                
                // Helper function to format bytes to human-readable format
                function formatBytes(bytes, decimals = 2) {{
                    if (bytes === 0) return '0 Bytes';
                    
                    const k = 1024;
                    const dm = decimals < 0 ? 0 : decimals;
                    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
                    
                    const i = Math.floor(Math.log(bytes) / Math.log(k));
                    
                    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
                }}
            }})();
        </script>
    </div>
    """


def list_users_directory(request, path="home"):
    """
    List the top-level users directory (/home/)

    Args:
        request: Django request
        path: Path to the users directory (home/)

    Returns:
        HttpResponse: Rendered HTML with users directory listing
    """
    # Convert path to OS specific
    os_specific_path = convert_path_to_os_specific(path)
    logger.info(f"Listing users directory: {path} -> {os_specific_path}")

    try:
        # Get directory contents
        list_of_files = os.listdir(os_specific_path)
        list_of_files.sort()

        # Filter out system files and hidden files
        list_of_files = [f for f in list_of_files if not f.startswith(".")]

        collect_files = "<h2>User Directories</h2>"
        collect_files += "<p>Select a user directory to proceed:</p>"

        # Only allow admins to create directories and upload files at the top level
        if request.user.is_authenticated and request.user.is_staff:
            collect_files += generate_create_directory_form("home")
            collect_files += generate_file_upload_form("home")

        # List each user directory with a link
        for item in list_of_files:
            full_path = os.path.join(os_specific_path, item)
            if os.path.isdir(full_path):
                collect_files += f'<li><a href="{item}/">{item}</a> (user directory)</li>'

        # If no users found
        if not any(os.path.isdir(os.path.join(os_specific_path, item)) for item in list_of_files):
            collect_files += "<li><b>No user directories found.</b></li>"
            collect_files += "<li>Please create a user directory structure: /home/username/species/project</li>"

            # Add authenticated user auto-creation
            if request.user.is_authenticated:
                current_user = request.user.username
                user_dir_path = os.path.join(os_specific_path, current_user)

                # Check if user directory exists, if not, create it from template
                if not os.path.exists(user_dir_path):
                    success = ensure_user_directory_exists(current_user)
                    if success:
                        collect_files += f'<li><a href="{current_user}/">User directory for {current_user} (created from template)</a></li>'
                        logger.info(f"Created user directory for {current_user} from template")
                    else:
                        collect_files += f'<li><a href="{current_user}/">Create directory for {current_user}</a></li>'
                        logger.warning(f"Failed to create user directory from template for {current_user}")
                else:
                    collect_files += (
                        f'<li><a href="{current_user}/">Go to your user directory ({current_user})</a></li>'
                    )
            else:
                collect_files += "<li>Please login to access your user directory</li>"

        return render(request, "listBC.html", {"listicle": mark_safe(collect_files)})

    except Exception as e:
        logger.error(f"Error in list_users_directory: {str(e)}")
        return render(request, "listBC.html", {"listicle": mark_safe(f"<li>Error: {str(e)}</li>")})


def list_species_directory(request, path, username):
    """
    List the species directories within a user directory (/home/username/)

    Args:
        request: Django request
        path: Path to the user's directory (home/username/)
        username: Username of the directory owner

    Returns:
        HttpResponse: Rendered HTML with species directory listing
    """
    # Convert path to OS specific
    os_specific_path = convert_path_to_os_specific(path)
    logger.info(f"Listing species directory: {path} -> {os_specific_path}")

    try:
        # Get directory contents
        list_of_files = os.listdir(os_specific_path)
        list_of_files.sort()

        # Get available species templates for reference
        available_species_list = available_species()

        collect_files = f"<h2>Species Directories for User: {username}</h2>"
        collect_files += "<p>Select a species directory:</p>"

        # Add forms for directory creation and file upload
        collect_files += generate_create_directory_form(f"home/{username}")
        collect_files += generate_file_upload_form(f"home/{username}")

        # List each species directory with a link
        for item in list_of_files:
            # Skip hidden files
            if item.startswith("."):
                continue

            full_path = os.path.join(os_specific_path, item)
            if os.path.isdir(full_path):
                is_recognized = item in available_species_list
                if is_recognized:
                    # Recognized species - make clickable with green label
                    collect_files += (
                        f'<li><a href="{item}/">{item}</a> <span style="color: green;">(recognized species)</span></li>'
                    )
                else:
                    # Non-recognized species - still clickable but with a note
                    collect_files += f'<li><a href="{item}/">{item}</a> <span style="color: #888;">(unrecognized species)</span></li>'

        # If no species directories found
        if not any(
            os.path.isdir(os.path.join(os_specific_path, item)) and not item.startswith(".") for item in list_of_files
        ):
            collect_files += f"<li><b>No species folders found in user directory: {username}.</b></li>"
            collect_files += "<li>Please create species folders within this directory.</li>"

            # Show available species templates
            if available_species_list:
                collect_files += "<li><b>Available species templates:</b></li>"
                for species in available_species_list:
                    collect_files += (
                        f'<li><a href="{species}/">{species}</a> [<a href="/species-info/{species}/">Info</a>]</li>'
                    )

        return render(request, "listBC.html", {"listicle": mark_safe(collect_files)})

    except Exception as e:
        logger.error(f"Error in list_species_directory: {str(e)}")
        return render(request, "listBC.html", {"listicle": mark_safe(f"<li>Error: {str(e)}</li>")})


def list_project_directory(request, path, username, species):
    """
    List the contents of a project directory or any directory containing WAV files
    (/home/username/species/... and deeper)

    Args:
        request: Django request
        path: Path to the project directory
        username: Username of the directory owner
        species: Species name

    Returns:
        HttpResponse: Rendered HTML with project directory listing
    """
    # Convert path to OS specific
    os_specific_path = convert_path_to_os_specific(path)
    logger.info(f"Listing project directory: {path} -> {os_specific_path}")

    try:
        # Get directory contents
        list_of_files = os.listdir(os_specific_path)
        list_of_files.sort()

        # Check available species for reference
        available_species_list = available_species()
        is_recognized_species = species in available_species_list

        collect_files = f"<h2>Project Directory: {os.path.basename(os_specific_path)}</h2>"
        if not is_recognized_species:
            collect_files += f'<div style="background-color: #fff3cd; padding: 10px; border-left: 5px solid #ffc107; margin-bottom: 15px;">'
            collect_files += (
                f'<p><strong>Warning:</strong> Species folder "{species}" is not a recognized species template.</p>'
            )
            collect_files += "</div>"

        # Add forms for directory creation and file upload
        collect_files += generate_create_directory_form(path)
        collect_files += generate_file_upload_form(path)

        # Check if this directory contains WAV files
        has_wav_files = any(item.lower().endswith(".wav") for item in list_of_files)
        if has_wav_files:
            collect_files += '<div style="margin: 10px 0; padding: 15px; background-color: #1e1e1e; border-left: 4px solid #3498db; border-radius: 5px;">'
            collect_files += '<h3 style="color: #e57373; margin-top: 0;">WAV File Guide:</h3>'
            collect_files += '<ul style="color: white; margin-bottom: 0;">'
            collect_files += '<li><strong style="color: #4CAF50;">Green</strong> items are clickable WAV files with paired pickle files containing call data.</li>'
            collect_files += "<li>Pickle files contain the call starts, stops, and labels for the WAV files.</li>"
            collect_files += (
                "<li>To make a WAV file clickable, it needs a matching pickle file (filename.wav.pickle).</li>"
            )
            collect_files += "</ul>"
            collect_files += "</div>"

        # Process files and subdirectories
        for item in list_of_files:
            # Skip hidden files
            if item.startswith("."):
                continue

            full_path = os.path.join(os_specific_path, item)

            # Determine item type and format accordingly
            if os.path.isdir(full_path):
                collect_files += '<li><a href="' + item + '/">' + item + "</a> (folder)</li>"
            elif item.lower().endswith(".wav") and os.path.isfile(full_path + ".pickle"):
                collect_files += (
                    '<li><a href="'
                    + item
                    + '">'
                    + item
                    + '</a> <span style="color: green;">(clickable: has paired pickle file with call data)</span></li>'
                )
            elif item.lower().endswith(".wav"):
                collect_files += (
                    "<li>"
                    + item
                    + ' <span style="color: #888;">(not clickable: missing paired pickle file)</span></li>'
                )
            elif item.lower().endswith(".pickle"):
                if item.lower().endswith(".wav.pickle"):
                    # This is a pickle file for a wav file
                    wav_file = item[:-7]  # Remove .pickle from the end
                    wav_path = os.path.join(os_specific_path, wav_file)
                    if os.path.isfile(wav_path):
                        collect_files += (
                            "<li>"
                            + item
                            + ' <span style="color: #0066cc;">(pickle file that defines call starts, stops, and labels for the WAV file)</span></li>'
                        )
                    else:
                        collect_files += (
                            "<li>"
                            + item
                            + ' <span style="color: #888;">(pickle file missing its paired WAV file)</span></li>'
                        )
                else:
                    # Other pickle files
                    collect_files += "<li>" + item + ' <span style="color: #888;">(pickle file)</span></li>'
            else:
                collect_files += "<li>" + item + "</li>"

        # If no files were found after filtering
        if not any(not item.startswith(".") for item in list_of_files):
            collect_files += f"<li><b>No data found in this directory.</b></li>"
            collect_files += "<li>Please add WAV files and their corresponding pickle files.</li>"

            # Add navigation links
            collect_files += f'<li><a href="/user/{username}/">Return to user directory</a></li>'

        return render(request, "listBC.html", {"listicle": mark_safe(collect_files)})

    except Exception as e:
        logger.error(f"Error in list_project_directory: {str(e)}")
        return render(request, "listBC.html", {"listicle": mark_safe(f"<li>Error: {str(e)}</li>")})
