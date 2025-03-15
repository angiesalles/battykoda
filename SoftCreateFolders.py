import os
import sys

def soft_create_folders(newpath):
    """
    Create directory structure if it doesn't exist, with better error handling.
    """
    if not newpath:
        print("ERROR: Empty path provided to soft_create_folders", file=sys.stderr)
        return False
        
    try:
        if not os.path.exists(newpath):
            print(f"Creating directory: {newpath}")
            os.makedirs(newpath, exist_ok=True)
            return True
        return True
    except Exception as e:
        print(f"ERROR creating directory {newpath}: {str(e)}", file=sys.stderr)
        return False

