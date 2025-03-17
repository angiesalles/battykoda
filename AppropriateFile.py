import urllib.parse
import re
import os
import logging
import utils

# Set up logging
logger = logging.getLogger('battykoda.appropriate_file')

def appropriate_file(path, args, folder_only=False):
    """
    Create an appropriate file path for temporary files.
    
    Args:
        path: Path to WAV file (from wav_path parameter)
        args: URL arguments
        folder_only: If True, return only the folder path
        
    Returns:
        str: Path to the temporary file or folder
    """
    # Use the proper OS standard temp directory via tempfile module
    import tempfile
    
    # Get the system temp directory (platform-independent)
    base_temp_dir = tempfile.gettempdir()
    
    # Create a battykoda subfolder in the temp directory
    temp_dir = os.path.join(base_temp_dir, "battykoda_temp")
    
    # Create the temp directory if it doesn't exist
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir, exist_ok=True)
        
    # Log the temp dir location during the first creation
    if not hasattr(appropriate_file, "_logged_temp_dir"):
        logger.info(f"Using temp directory: {temp_dir}")
        appropriate_file._logged_temp_dir = True
    
    # Convert the path to use the correct home directory format
    path_parts = path.split('/')
    
    # If the path starts with 'home/', convert it to the OS-specific format
    # This is critical for macOS where we need 'Users' instead of 'home'
    if len(path_parts) > 1 and path_parts[0] == 'home':
        # Replace 'home' with the correct directory for this OS
        path_parts[0] = utils.get_home_directory()
        
        # Reconstruct the path with the corrected home directory
        corrected_path = '/'.join(path_parts)
        logger.debug(f"Converted path from '{path}' to '{corrected_path}'")
        path = corrected_path
    
    # Build the folder path in the temp directory
    folder = os.path.join(temp_dir, *path.split('/'))
    
    if folder_only:
        return folder
    
    # Determine file extension based on arguments
    file_extension = '.png'  # Default for spectrograms
    if 'loudness' in args:
        file_extension = '.wav'  # For audio files
        
    # Create a unique filename based on the provided arguments
    args_encoded = re.sub('[?&=]', '_', urllib.parse.urlencode(args))
    filename = f"{args_encoded}{file_extension}"
    
    # Create the full file path
    file_path = os.path.join(folder, filename)
    
    return file_path

