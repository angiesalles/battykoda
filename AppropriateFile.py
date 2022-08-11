import urllib.parse
import re


def appropriate_file(path, args, osfolder, folder_only=False):
    folder = osfolder + 'tempdata/' + '/'.join(path.split('/')[:-1])

    if folder_only:
        return folder
    return folder + '/' + re.sub('[?&=]', '_',  urllib.parse.urlencode(args)) + path.split('/')[-1]

