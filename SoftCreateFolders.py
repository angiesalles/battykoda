import os
def soft_create_folders(newpath):
    if not os.path.exists(newpath):
        os.makedirs(newpath)

