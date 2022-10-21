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
        return GetListing.get_listing(path, osfolder, path)
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
    if not exists(appropriate_file(path, request.args, osfolder)):
        SoftCreateFolders.soft_create_folders(appropriate_file(path, request.args, osfolder, folder_only=True))
        call_to_do = int(request.args['call'])
        overview = request.args['overview'] == 'True'
        hwin = Hwin.overview_hwin if overview else Hwin.normal_hwin
        thr_x1, fs, hashof = GetAudioBit.get_audio_bit(osfolder + os.sep.join(path.split('/')[:-1]), call_to_do, hwin)
        thr_x1 = thr_x1[:, int(request.args['channel'])]
        assert request.args['hash'] == hashof
        scipy.io.wavfile.write(appropriate_file(path, request.args, osfolder),
                               fs // 10,
                               thr_x1.astype('float32').repeat(10) * float(request.args['loudness']))

    return send_file(appropriate_file(path, request.args, osfolder))


if __name__ == '__main__':
    mainfunction()
