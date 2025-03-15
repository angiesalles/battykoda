import os
from flask import Flask, render_template, request, send_file
import scipy.signal
import scipy.io
from os.path import exists
import FileList
import GetAudioBit
import platform
import threading
import queue
import SoftCreateFolders
import StoreTask
import GetTask
from AppropriateFile import appropriate_file
import Workers
import Hwin
import htmlGenerator
import GetListing
from datetime import datetime
import pickle
import csv

# Set appropriate OS folder and system-specific paths
computer_system = platform.system()
if computer_system == 'Windows':
    osfolder = '.\\data\\'
    home_path = 'home'  # Will be used for virtual path structure
elif computer_system == 'Darwin':  # macOS
    osfolder = '/'
    home_path = 'Users'  # Use Users directory on macOS
else:  # Linux or other Unix-like systems
    osfolder = '/'
    home_path = 'home'

app = Flask(__name__, static_folder='static')
global_user_setting = {'limit_confidence': '90',
                       'user_name': "",
                       'contrast': '4',
                       'loudness': '0.5',
                       'main': '1'}

global_request_queue = queue.PriorityQueue()
global_work_queue = queue.PriorityQueue()



def mainfunction():
    # from werkzeug.middleware.profiler import ProfilerMiddleware
    # app.wsgi_app = ProfilerMiddleware(app.wsgi_app)
    threading.Thread(target=Workers.worker,
                     args=(global_request_queue, global_work_queue, osfolder),
                     daemon=True).start()
    threading.Thread(target=Workers.worker2,
                     args=(global_work_queue, ),
                     daemon=True).start()
    app.run(host='0.0.0.0', debug=False, port=8060)


@app.route('/')
def mainpage():
    # Get available species and generate links
    available_species = htmlGenerator.available_species()
    species_links = ""
    
    # Add a section for user directories
    species_links += '<li><b>User Directories:</b></li>'
    
    # Get current username from the system
    import getpass
    import os
    current_user = getpass.getuser()
    
    # Add a link to the current user's directory
    species_links += f'<li><a href="/battykoda/home/{current_user}/"><strong>Your Directory</strong> ({current_user})</a></li>'
    
    # Get all user directories from the system
    try:
        if platform.system() == "Darwin":  # macOS
            user_dir = "/Users"
            users = os.listdir(user_dir)
            # Filter out system directories
            users = [u for u in users if not u.startswith('.') and u != 'Shared' and u != current_user]
            users.sort()
            
            # Add other user directories
            if users:
                for user in users:
                    if os.path.isdir(os.path.join(user_dir, user)):
                        species_links += f'<li><a href="/battykoda/home/{user}/">{user}</a></li>'
    except (FileNotFoundError, PermissionError):
        pass
    
    # Add available species templates section
    if available_species:
        species_links += '<li><b>Available Species Templates:</b></li>'
        for species in available_species:
            species_links += f'<li><a href="/battykoda/home/{current_user}/{species}/">{species}</a></li>'
    else:
        species_links += '<li>No species templates available. Please check the static folder.</li>'
    
    return render_template('welcometoBK.html', species_links=species_links)


@app.route('/battykoda/<path:path>', methods=['POST', 'GET'])
def handle_batty(path):
    global global_user_setting
    user_setting = global_user_setting
    
    try:
        # Replace 'home/' with the appropriate system home path
        if path == 'home/':
            modified_path = home_path + '/'
        else:
            modified_path = path.replace('home/', home_path + '/')
    except Exception as e:
        # Handle any unexpected errors in path modification
        print(f"Error processing path {path}: {str(e)}")
        modified_path = path  # Fall back to original path if there's an error
    
    if os.path.isdir(osfolder + modified_path):
        return FileList.file_list(osfolder, modified_path, path)
    if path.endswith('review.html'):
        if request.method == 'POST':
            # Replace 'home/' with the appropriate system home path
            mod_path = path.replace('home/', home_path + '/')
            path_to_file = osfolder + '/'.join(mod_path.split('/')[:-1])
            with open(path_to_file + '.pickle', 'rb') as pfile:
                segment_data = pickle.load(pfile)
            type_c = path.split('/')[-1][:-12]
            for idx in range(len(segment_data['labels'])):
                if segment_data['labels'][idx]['type_call'] == type_c:
                    if 'call_' + str(idx) in request.form:
                        segment_data['labels'][idx] = dict(segment_data['labels'][idx])
                        segment_data['labels'][idx]['type_call'] = 'Unsure'
            with open(path_to_file + '.pickle', 'wb') as pfile:
                pickle.dump(segment_data, pfile)
            data_pre = segment_data
            data = []
            for idx in range(len(data_pre['onsets'])):
                data.append(
                    [data_pre['onsets'][idx], data_pre['offsets'][idx], data_pre['labels'][idx]['type_call']])
            with open(path_to_file + '.csv', 'w') as f:
                writer = csv.writer(f)
                writer.writerows(data)
        return GetListing.get_listing(path_to_file=osfolder + path,
                                      osfolder=osfolder,
                                      path=path)
    if request.method == 'POST':
        user_setting = request.form.copy()
        if 'submitbutton' in request.form:
            StoreTask.store_task(osfolder + path[:-1], request.form)
    # Replace 'home/' with the appropriate system home path for the task
    mod_path = path.replace('home/', home_path + '/')
    return GetTask.get_task(path_to_file=osfolder + mod_path[:-1],
                            path=path,  # Keep original path for URLs
                            user_setting=user_setting,
                            osfolder=osfolder,
                            undo=('undobutton' in request.form))


@app.route('/img/<path:path>', methods=['GET'])
def handle_image(path):
    # Replace 'home/' with the appropriate system home path
    mod_path = path.replace('home/', home_path + '/')
    
    priority_part = 0 if int(request.args['channel']) == int(global_user_setting['main'])-1 else 2
    overview_part = 1 if request.args['overview'] == '1' else 0
    workload = {'path': mod_path, 'args': request.args}
    global_request_queue.put(Workers.PrioItem(priority_part + overview_part, workload))
    call_to_do = int(request.args['call'])
    if call_to_do + 1 < int(request.args['numcalls']):
        new_args = request.args.copy()
        new_args['call'] = str(call_to_do+1)
        global_request_queue.put(Workers.PrioItem(4 + priority_part, {'path': mod_path, 'args': new_args}))
    global_request_queue.join()
    workload['thread'].join()
    return send_file(appropriate_file(path, request.args, osfolder))


@app.route('/audio/<path:path>')
def handle_sound(path):
    # Replace 'home/' with the appropriate system home path
    mod_path = path.replace('home/', home_path + '/')
    
    slowdown = 5
    if not exists(appropriate_file(path, request.args, osfolder)):
        SoftCreateFolders.soft_create_folders(appropriate_file(path, request.args, osfolder, folder_only=True))
        call_to_do = int(request.args['call'])
        overview = request.args['overview'] == 'True'
        hwin = Hwin.overview_hwin if overview else Hwin.normal_hwin
        
        # Use the modified path with correct home directory
        audio_path = osfolder + os.sep.join(mod_path.split('/')[:-1])
        thr_x1, fs, hashof = GetAudioBit.get_audio_bit(audio_path, call_to_do, hwin)
        
        thr_x1 = thr_x1[:, int(request.args['channel'])]
        assert request.args['hash'] == hashof
        scipy.io.wavfile.write(appropriate_file(path, request.args, osfolder),
                               fs // slowdown,
                               thr_x1.astype('float32').repeat(slowdown) * float(request.args['loudness']))

    return send_file(appropriate_file(path, request.args, osfolder))


if __name__ == '__main__':
    mainfunction()
