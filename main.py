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
import traceback

osfolder = '/'
computer = platform.uname()
if computer.system == 'Windows':
    osfolder = '.\\data\\'

app = Flask(__name__, static_folder=osfolder + htmlGenerator.static_folder)
global_user_setting = {'limit_confidence': '90',
                       'user_name': "",
                       'contrast': '4',
                       'loudness': '0.5',
                       'main': '1'}

global_request_queue = queue.PriorityQueue()
global_work_queue = queue.PriorityQueue()


@app.errorhandler(Exception)
def handle_exception(e):
    # Create a timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    crash_file = f"crash_state_{timestamp}.pkl"

    # Serialize relevant state to the file
    state = {
        "timestamp": timestamp,
        "exception": str(e),
        "stack_trace": traceback.format_exc(),
        "env": dict(os.environ),  # Current environment variables
        "request_data": request.get_json() if request.is_json else request.data.decode(),
    }
    with open(crash_file, "wb") as f:
        pickle.dump(state, f)

    # Log to console or any other logging mechanism
    print(f"Crash data saved to {crash_file}")

    return f"An error occurred. State has been saved to {crash_file}.", 500


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
    return render_template('welcometoBK.html', data=dict())


@app.route('/battykoda/<path:path>', methods=['POST', 'GET'])
def handle_batty(path):
    global global_user_setting
    user_setting = global_user_setting
    if os.path.isdir(osfolder + path):
        return FileList.file_list(osfolder, path)
    if path.endswith('review.html'):
        if request.method == 'POST':
            path_to_file = osfolder + '/'.join(path.split('/')[:-1])
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
    return GetTask.get_task(path_to_file=osfolder + path[:-1],
                            path=path,
                            user_setting=user_setting,
                            osfolder=osfolder,
                            undo=('undobutton' in request.form))


@app.route('/img/<path:path>', methods=['GET'])
def handle_image(path):
    priority_part = 0 if int(request.args['channel']) == int(global_user_setting['main'])-1 else 2
    overview_part = 1 if request.args['overview'] == '1' else 0
    workload = {'path': path, 'args': request.args}
    global_request_queue.put(Workers.PrioItem(priority_part + overview_part, workload))
    call_to_do = int(request.args['call'])
    if call_to_do + 1 < int(request.args['numcalls']):
        new_args = request.args.copy()
        new_args['call'] = str(call_to_do+1)
        global_request_queue.put(Workers.PrioItem(4 + priority_part, {'path': path, 'args': new_args}))
    global_request_queue.join()
    workload['thread'].join()
    return send_file(appropriate_file(path, request.args, osfolder))


@app.route('/audio/<path:path>')
def handle_sound(path):
    slowdown = 5
    if not exists(appropriate_file(path, request.args, osfolder)):
        SoftCreateFolders.soft_create_folders(appropriate_file(path, request.args, osfolder, folder_only=True))
        call_to_do = int(request.args['call'])
        overview = request.args['overview'] == 'True'
        hwin = Hwin.overview_hwin if overview else Hwin.normal_hwin
        thr_x1, fs, hashof = GetAudioBit.get_audio_bit(osfolder + os.sep.join(path.split('/')[:-1]), call_to_do, hwin)
        thr_x1 = thr_x1[:, int(request.args['channel'])]
        assert request.args['hash'] == hashof
        scipy.io.wavfile.write(appropriate_file(path, request.args, osfolder),
                               fs // slowdown,
                               thr_x1.astype('float32').repeat(slowdown) * float(request.args['loudness']))

    return send_file(appropriate_file(path, request.args, osfolder))


if __name__ == '__main__':
    mainfunction()
