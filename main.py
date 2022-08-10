import os
import tempfile
import thresholding
import htmlGenerator as hG
from flask import Flask, render_template, request, Markup, send_from_directory, send_file
import pickle
import numpy as np
import random
import matplotlib.pyplot as plt
import scipy.signal
import scipy.io
from os.path import exists
import DataReader
import matplotlib
import platform
import threading
import queue
import urllib.parse
from dataclasses import dataclass, field
from typing import Any
import re


@dataclass(order=True)
class PrioItem:
    priority: int
    item: Any = field(compare=False)


# Force matplotlib to not use any Xwindows backend.
# https://stackoverflow.com/questions/2801882/generating-a-png-with-matplotlib-when-display-is-undefined
matplotlib.use('Agg')

global_threshold = 0.01


osfolder = '/Users/angelessalles/Documents/data/'
computer = platform.uname()
if computer.system == 'Windows':
    osfolder = '.\\data\\'

app = Flask(__name__, static_folder=osfolder + 'static')
global_limit_confidence = 90
global_user_name = ""
lookup = dict()
global_contrast = 4
global_loudness = 0.5
global_main = 0
global_request_queue = queue.PriorityQueue()
global_work_queue = queue.PriorityQueue()


def get_audio_bit(path_to_file, call_to_do, hwin):
    audiodata, fs, hashof = DataReader.DataReader.data_read(path_to_file)
    with open(path_to_file + '.pickle', 'rb') as pfile:
        segment_data = pickle.load(pfile)
    onset = (segment_data['onsets'][call_to_do] * fs).astype(int)
    offset = (segment_data['offsets'][call_to_do] * fs).astype(int)

    thr_x1 = audiodata[max(0, onset - (fs * hwin // 1000)):min(offset + (fs * hwin // 1000), len(audiodata)), :]
    return thr_x1, fs, hashof


def soft_create_folders(newpath):
    if not os.path.exists(newpath):
        os.makedirs(newpath)


def store_task(path_to_file, result):

    with open(path_to_file + '.pickle', 'rb') as pfile:
        segment_data = pickle.load(pfile)
    segment_data['labels'].append(result)
    with open(path_to_file+'.pickle', 'wb') as pfile:
        pickle.dump(segment_data, pfile)

    # newpath = sppath + os.sep + 'classifier'
    # soft_create_folders(newpath)
    #
    # call_to_do = len(segment_data['labels'])
    # thrX1, fs = get_audio_bit(path_to_file, call_to_do, 0)
    # scipy.io.wavfile.write(newpath + os.sep + '.'.join(browpath.replace('/','_').split('.')[:-1]) + str(onset) +'_'+\
    # result['type_call'] + '.wav', fs, thrX1)#ask gabby if she needs buffer around sound


def get_task(path_to_file, path, undo=False):
    global global_contrast
    global global_user_name
    global global_limit_confidence
    global global_main
    with open(path_to_file + '.pickle', 'rb') as pfile:
        segment_data = pickle.load(pfile)
    assumed_answer = 'Echo'
    if undo:
        popped = segment_data['labels'].pop()
        assumed_answer = popped['type_call']
        with open(path_to_file + '.pickle', 'wb') as pfile:
            pickle.dump(segment_data, pfile)
    call_to_do = len(segment_data['labels'])
    if call_to_do == len(segment_data['offsets']):
        return render_template('endFile.html',
                               data={'filedirectory': '/battykoda/' + '/'.join(path.split('/')[:-2]) + '/'})
    backfragment = ''
    if call_to_do > 0:
        backfragment = Markup('<a href="/battykoda/back/'+path+'">Undo</a>')
    txtsp, jpgsp = hG.spgather(path, osfolder, assumed_answer)
    thr_x1, _, hashof = get_audio_bit(osfolder + os.sep.join(path.split('/')[:-1]), call_to_do, 0)
    global_main = min(global_main, thr_x1.shape[1]-1)

    def spectr_particle_fun(_channel, _overview):
        args = {'hash': hashof,
                'call': call_to_do,
                'channel': _channel,
                'overview': _overview,
                'contrast': global_contrast,
                'numcalls': len(segment_data['offsets'])}
        return '/img/' + path + 'spectrogram.png?' + urllib.parse.urlencode(args)

    def audio_particle_fun(_channel):
        args = {'hash': hashof,
                'channel': _channel,
                'call': call_to_do,
                'loudness': global_loudness}
        return '/audio/' + path + 'snippet.wav?' + urllib.parse.urlencode(args)
    others = np.setdiff1d(range(thr_x1.shape[1]), global_main)
    other_html = ['<p><img src="'+spectr_particle_fun(other, _overview=False)+'" width="600" height="250" >' +
                  '<audio controls src="' + audio_particle_fun(other) + '" preload="none" /></p>' for other in others]
    data = {'spectrogram': spectr_particle_fun(global_main, _overview=False),
            'spectrogram_large': spectr_particle_fun(global_main, _overview=True),
            'confidence': str(random.randint(0, 100)),  # this is bongo code
            'limit_confidence': str(global_limit_confidence),
            'currentcall': call_to_do,
            'totalcalls': len(segment_data['offsets']),
            'contrast': str(global_contrast),
            'loudness': str(global_loudness),
            'backlink': backfragment,
            'audiolink': audio_particle_fun(global_main),
            'user_name': global_user_name,
            'species': Markup(txtsp),
            'jpgname': jpgsp,
            'focused': assumed_answer,
            'main': global_main+1,
            'max_main': thr_x1.shape[1],
            'others': Markup(''.join(other_html)),
            }
    return render_template('AngieBK.html', data=data)


def index(path_to_file, path, is_post, undo=False):
    global global_user_name
    global global_limit_confidence
    global global_contrast
    global global_loudness
    global global_main
    if not is_post:
        return get_task(path_to_file, path, undo)

    result = request.form
    if result['user_name'] == '':
        return '''
      <html>
      <body>Please enter annotator name
      </body>
      </html>
      '''
    global_user_name = result['user_name']
    global_limit_confidence = result['limit_confidence']
    global_contrast = float(result['contrast'])
    global_loudness = float(result['loudness'])
    global_main = int(result['main']) - 1
    store_task(path_to_file, result)
    return index(path_to_file, path, False)


def appropriate_file(path, args, folder_only=False):
    folder = osfolder + 'tempdata/' + '/'.join(path.split('/')[:-1])

    if folder_only:
        return folder
    return folder + '/' + re.sub('[?&=]', '_',  urllib.parse.urlencode(args)) + path.split('/')[-1]


@app.route('/audio/<path:path>')
def handle_sound(path):
    if not exists(appropriate_file(path, request.args)):
        soft_create_folders(appropriate_file(path, request.args, folder_only=True))
        call_to_do = int(request.args['call'])
        thr_x1, fs, hashof = get_audio_bit(osfolder + os.sep.join(path.split('/')[:-1]), call_to_do, 10)
        thr_x1 = thr_x1[:, int(request.args['channel'])]
        assert request.args['hash'] == hashof
        scipy.io.wavfile.write(appropriate_file(path, request.args),
                               fs // 10,
                               thr_x1.astype('float32').repeat(10) * float(request.args['loudness']))

    return send_file(appropriate_file(path, request.args))


def plotting(path, args, event):
    event.wait()
    overview = args['overview'] == 'True'
    call_to_do = int(args['call'])
    contrast = float(args['contrast'])
    hwin = 50 if overview else 10
    thr_x1, fs, hashof = get_audio_bit(osfolder + os.sep.join(path.split('/')[:-1]), call_to_do, hwin)
    thr_x1 = thr_x1[:, int(args['channel'])]
    assert args['hash'] == hashof
    f, t, sxx = scipy.signal.spectrogram(thr_x1, fs, nperseg=2 ** 8, noverlap=254, nfft=2 ** 8)
    plt.figure(facecolor='black')
    ax = plt.axes()
    ax.set_facecolor('indigo')
    temocontrast = 10 ** contrast
    plt.pcolormesh(t, f, np.arctan(temocontrast * sxx), shading='auto')
    if not overview:
        plt.xlim(0, 0.050)
    ax.tick_params(axis='x', colors='white')
    ax.tick_params(axis='y', colors='white')
    ax.xaxis.label.set_color('white')
    ax.yaxis.label.set_color('white')
    plt.ylabel('Frequency [Hz]')
    plt.xlabel('Time [sec]')
    soft_create_folders(appropriate_file(path, args, folder_only=True))
    plt.savefig(appropriate_file(path, args))


def worker():
    mythreadstorage = {}
    while True:
        pi = global_request_queue.get()
        key = appropriate_file(pi.item['path'], pi.item['args'])
        if key not in mythreadstorage:
            event = threading.Event()
            thread = threading.Thread(target=plotting,
                                      args=(pi.item['path'], pi.item['args'], event),
                                      daemon=True)
            thread.start()
            mythreadstorage[key] = thread
            global_work_queue.put(PrioItem(pi.priority, {'thread': thread, 'event': event}))
        pi.item['thread'] = mythreadstorage[key]
        global_request_queue.task_done()


def worker2():
    while True:
        item = global_work_queue.get().item
        item['event'].set()
        item['thread'].join()
        global_work_queue.task_done()


@app.route('/img/<path:path>', methods=['GET'])
def handle_image(path):

    priority_part = 0 if int(request.args['channel']) == global_main else 2
    overview_part = 1 if request.args['overview'] == '1' else 0
    workload = {'path': path, 'args': request.args}
    global_request_queue.put(PrioItem(priority_part + overview_part, workload))
    call_to_do = int(request.args['call'])
    if call_to_do + 1 < int(request.args['numcalls']):
        new_args = request.args.copy()
        new_args['call'] = str(call_to_do+1)
        global_request_queue.put(PrioItem(4 + priority_part,
                                          {'path': path, 'args': new_args}))
    global_request_queue.join()
    workload['thread'].join()
    return send_file(appropriate_file(path, request.args))


@app.route('/thres/<path:path>')
def thresholding():
    return send_from_directory('/'.join(lookup[request.path[4:]].split(os.sep)[:-1]), request.path[4:])


@app.route('/battykoda/<path:path>', methods=['POST', 'GET'])
def static_cont(path):
    if os.path.isdir(osfolder + path):
        list_of_files = os.listdir(osfolder + path)
        list_of_files.sort()
        collect_files = ''
        for item in list_of_files:
            if item.endswith('.pickle') or item.endswith('DS_Store'):
                continue
            collect_files += '<li><a href="'+item+'/">'+item+'</a></li>'

        return render_template('listBK.html', data={'listicle': Markup(collect_files)})

    if path.startswith('back/'):
        return index(osfolder + path[5:-1], path[5:], request.method == 'POST', undo=True)
    if exists(osfolder + path[:-1] + '.pickle'):
        return index(osfolder + path[:-1], path, request.method == 'POST')
    if request.method == 'POST':
        result = request.form
        threshold = float(result['threshold_nb'])
        if result['threshold'] == 'correct':
            audiodata, fs = DataReader.DataReader.data_read(osfolder + path[:-1])
            smood_audio = thresholding.SmoothData(audiodata, fs)

            onsets, offsets = thresholding.SegmentNotes(smood_audio, fs, threshold)

            f = open(osfolder + path[:-1] + '.pickle', 'wb')
            pickle.dump({'threshold': threshold,
                         'onsets': onsets,
                         'offsets': offsets,
                         'labels': [],
                         'startFrq': [],
                         'endFrq': []}, f)
            f.close()

            return index(osfolder + path[:-1], path, False)

    audiodata, fs = DataReader.DataReader.data_read(osfolder + path[:-1])
    audiodata = audiodata[:, 0]
    smood_audio = thresholding.SmoothData(audiodata, fs)

    listims = []
    boink = []
    plttitle = ['start', 'middle', 'end']
    seg_len = 100000
    for idx in range(3):
        tf = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        plt.figure(figsize=(3, 3))
        if idx == 0:
            boink = idx
        if idx == 1:
            boink = audiodata.shape[0] // 2
        if idx == 2:
            boink = audiodata.shape[0] - 2 * seg_len
        plt.plot(smood_audio[0 + boink:seg_len + boink])
        plt.hlines(global_threshold, 0, seg_len, 'k')
        plt.title(plttitle[idx])
        plt.savefig(tf)
        shorty = tf.name.split(os.sep)[-1]
        lookup[shorty] = tf.name
        listims.append('/battykoda/thres/' + shorty)
        tf.close()

    return render_template('setThreshold.html',
                           data={'images': listims,
                                 'threshold': str(global_threshold)})


@app.route('/')
def mainpage():
    return render_template('welcometoBK.html', data=dict())


if __name__ == '__main__':

    # from werkzeug.middleware.profiler import ProfilerMiddleware
    # app.wsgi_app = ProfilerMiddleware(app.wsgi_app)
    threading.Thread(target=worker, daemon=True).start()
    threading.Thread(target=worker2, daemon=True).start()
    print(app.url_map)
    app.run(host='0.0.0.0', debug=False, port=8060)
