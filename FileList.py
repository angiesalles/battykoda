import os
import htmlGenerator
from flask import render_template, Markup


def file_list(osfolder, path):
    list_of_files = os.listdir(osfolder + path)
    list_of_files.sort()
    collect_files = ''
    for item in list_of_files:
        if item.endswith('.pickle') or item.endswith('DS_Store'):
            continue
        if path == 'home/' and item.endswith('lost+found'):
            continue
        if path == 'home/' and item.endswith('data'):
            continue
        if path.count('/') == 2 and item not in htmlGenerator.available_species(osfolder):
            continue
        collect_files += '<li><a href="' + item + '/">' + item + '</a></li>'

    return render_template('listBK.html', data={'listicle': Markup(collect_files)})