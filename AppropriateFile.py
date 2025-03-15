import urllib.parse
import re
import os
import platform


def appropriate_file(path, args, osfolder, folder_only=False):
    # Get the appropriate temp directory based on OS
    if platform.system() == "Darwin":  # macOS
        temp_dir = os.path.join(os.path.expanduser("~"), "battykoda_temp")
    elif platform.system() == "Windows":
        temp_dir = os.path.join(os.environ.get("TEMP", "C:\\temp"), "battykoda_temp")
    else:  # Linux
        temp_dir = "/tmp/battykoda_temp"
    
    # Create the temp directory if it doesn't exist
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir, exist_ok=True)
        
    # Build the path using the temp directory
    folder = os.path.join(temp_dir, *path.split('/')[:-1])

    if folder_only:
        return folder
    return os.path.join(folder, re.sub('[?&=]', '_', urllib.parse.urlencode(args)) + path.split('/')[-1])

