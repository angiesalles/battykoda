import os
import htmlGenerator
from flask import render_template, Markup


def file_list(osfolder, path):
    list_of_files = os.listdir(osfolder + path)
    list_of_files.sort()
    collect_files = ''
    for item in list_of_files:
        if '.git' in item:
            continue
        if path == 'home/' and item.endswith('lost+found'):
            continue
        if path == 'home/' and item.endswith('data'):
            continue
        if path.count('/') == 2 and item not in htmlGenerator.available_species(osfolder):
            continue
        if path.count('/') > 2 and path.split('/')[2] not in htmlGenerator.available_species(osfolder):
            continue
        if os.path.isdir('/' + path + item) or os.path.isfile('/' + path + item+'.pickle'):
            collect_files += '<li><a href="' + item + '/">' + item + '</a></li>'
        else:
            collect_files += '<li>' + item + '</li>'

    return render_template('listBK.html', data={'listicle': Markup(collect_files)})
