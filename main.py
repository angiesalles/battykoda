import os
import tempfile
import thresholding
import htmlGenerator as hG
from flask import Flask, render_template, request, url_for, redirect, Markup, send_from_directory, send_file
import pickle
import numpy as np
import random
import matplotlib.pyplot as plt
import scipy.signal
from os.path import exists
import DataReader
import matplotlib
import platform
import threading
import queue

from dataclasses import dataclass, field
from typing import Any

@dataclass(order=True)
class PrioritizedItem:
    priority: int
    item: Any=field(compare=False)

# Force matplotlib to not use any Xwindows backend.
# https://stackoverflow.com/questions/2801882/generating-a-png-with-matplotlib-when-display-is-undefined
matplotlib.use('Agg')

threshold = 0.01

app = Flask(__name__)
osfolder = '/Users/angelessalles/Documents/data/'
computer = platform.uname()
if computer.system == 'Windows':
    osfolder = '.\\data\\'
global_limit_confidence = 90
global_user_name = ""
lookup = dict()
global_contrast = 4
global_priority = 0
global_request_queue = queue.PriorityQueue()
global_work_queue = queue.PriorityQueue()

def get_audio_bit(path_to_file, call_to_do, hwin):
    audiodata, fs, hashof = DataReader.DataReader.data_read(path_to_file)
    with open(path_to_file + '.pickle', 'rb') as pfile:
        segmentData = pickle.load(pfile)
    onset = (segmentData['onsets'][call_to_do] * fs).astype(int)
    offset = (segmentData['offsets'][call_to_do] * fs).astype(int)

    thrX1 = audiodata[max(0, onset - (fs * hwin // 1000)):min(offset + (fs * hwin // 1000), len(audiodata)), :]
    return thrX1, fs, hashof

def soft_create_folders(newpath):
    if not os.path.exists(newpath):
        os.makedirs(newpath)

def store_task(path_to_file,result,sppath,browpath):

    with open(path_to_file + '.pickle', 'rb') as pfile:
        segmentData = pickle.load(pfile)
    segmentData['labels'].append(result)
    with open(path_to_file+'.pickle', 'wb') as pfile:
        pickle.dump(segmentData, pfile)


    # newpath = sppath + os.sep + 'classifier'
    # soft_create_folders(newpath)
    #
    # call_to_do = len(segmentData['labels'])
    # thrX1, fs = get_audio_bit(path_to_file, call_to_do, 0)
    # scipy.io.wavfile.write(newpath + os.sep + '.'.join(browpath.replace('/','_').split('.')[:-1]) + str(onset) +'_'+ result['type_call'] + '.wav', fs, thrX1)#ask gabby if she needs buffer around sound



def get_task(path_to_file, path, undo=False):
    global global_contrast
    global global_user_name
    global global_limit_confidence
    global global_priority
    with open(path_to_file + '.pickle', 'rb') as pfile:
        segmentData = pickle.load(pfile)
    assumed_answer = 'Echo'
    if undo:
        popped = segmentData['labels'].pop()
        assumed_answer = popped['type_call']
        with open(path_to_file + '.pickle', 'wb') as pfile:
            pickle.dump(segmentData, pfile)
    call_to_do = len(segmentData['labels'])
    if call_to_do == len(segmentData['offsets']):
        return render_template('endFile.html',
                               data={'filedirectory': '/battykoda/' + '/'.join(path.split('/')[:-2]) + '/'})
    backfragment = ''
    if call_to_do > 0:
        backfragment = Markup('<a href="/battykoda/back/'+path+'">Undo</a>')
    txtsp, jpgsp = hG.spgather(path, osfolder, assumed_answer)
    thrX1, _, hashof = get_audio_bit(osfolder + os.sep.join(path.split('/')[:-1]), call_to_do, 0)
    global_priority = min(global_priority, thrX1.shape[1]-1)
    def spectr_particle_fun(_channel):
        return path \
               + str(_channel) \
               + '/' \
               + str(len(segmentData['offsets'])) \
               + '/' \
               + hashof \
               + '/' \
               + str(global_contrast) \
               + '/' \
               + str(call_to_do) \
               + '.png'

    others = np.setdiff1d(range(thrX1.shape[1]), global_priority)
    other_html = ['<p><img src="/battykoda/img/'+spectr_particle_fun(other)+'" width="600" height="250" ></p>' for other in others]
    data = {'spectrogram': '/battykoda/img/' + spectr_particle_fun(global_priority),
            'spectrogram_large': '/battykoda/overview/' + spectr_particle_fun(global_priority),
            'confidence': str(random.randint(0, 100)),#this is bongo code needs to be replaced with real output of classifier
            'limit_confidence': str(global_limit_confidence),
            'currentcall': call_to_do,
            'totalcalls': len(segmentData['offsets']),
            'contrast': str(global_contrast),
            'backlink': backfragment,
            'audiolink': '/battykoda/audio/' + path + str(global_priority) + '/' + hashof + '/' + str(call_to_do) + '.wav',
            'user_name': global_user_name,
            'species': Markup(txtsp),
            'jpgname': jpgsp,
            'focused': assumed_answer,
            'priority': global_priority+1,
            'max_priority': thrX1.shape[1],
            'others': Markup(''.join(other_html)),
            }
    return render_template('AngieBK.html', data=data)


def index(path_to_file,path, is_post, undo=False):
    global global_user_name
    global global_limit_confidence
    global global_contrast
    global global_priority
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
    global_contrast = result['contrast']
    global_priority = int(result['priority']) - 1
    store_task(path_to_file,result,osfolder + path.split('/')[0] + os.sep + path.split('/')[1] + os.sep + path.split('/')[2],path)
    return index(path_to_file, path, False)


def handleSound(path):
    if not exists('tempdata'+os.sep+path):
        soft_create_folders('tempdata'+os.sep+ os.sep.join(path.split('/')[:-1]))
        call_to_do = int(path[:-4].split('/')[-1])
        thrX1, fs, hashof = get_audio_bit(osfolder + os.sep.join(path.split('/')[1:-3]), call_to_do, 10)
        thrX1 = thrX1[:, int(path[:].split('/')[-3])]
        assert path.split('/')[-2] == hashof
        scipy.io.wavfile.write('tempdata'+os.sep+path, fs // 10, thrX1.astype('float32').repeat(10)/2)

    return send_file('tempdata' + os.sep + path.replace('/', os.sep))

def plotting(path, event):
    event.wait()
    overview = path.startswith('overview/')
    call_to_do = int(path[:-4].split('/')[-1])
    contrast = float(path.split('/')[-2])
    hwin = 50 if overview else 10
    thrX1, fs, hashof = get_audio_bit(osfolder + os.sep.join(path.split('/')[1:-5]), call_to_do, hwin)
    thrX1 = thrX1[:,int(path.split('/')[-5])]
    assert path.split('/')[-3] == hashof
    f, t, Sxx = scipy.signal.spectrogram(thrX1, fs, nperseg=2 ** 8, noverlap=254, nfft=2 ** 8)
    plt.figure(facecolor='black')
    ax = plt.axes()
    ax.set_facecolor('indigo')
    temocontrast = 10 ** (float(contrast))
    plt.pcolormesh(t, f, np.arctan(temocontrast * Sxx), shading='auto')
    if not overview:
        plt.xlim(0, 0.050)
    ax.tick_params(axis='x', colors='white')
    ax.tick_params(axis='y', colors='white')
    ax.xaxis.label.set_color('white')
    ax.yaxis.label.set_color('white')
    plt.ylabel('Frequency [Hz]')
    plt.xlabel('Time [sec]')
    soft_create_folders('tempdata' + os.sep + os.sep.join(path.split('/')[:-1]))
    plt.savefig('tempdata' + os.sep + path.replace('/', os.sep))

def worker():
    mythreadstorage = {}
    while True:
        item = global_request_queue.get()
        if not item.item['path'] in mythreadstorage:
            event = threading.Event()
            thread = threading.Thread(target=plotting,
                                      args=(item.item['path'], event),
                                      daemon=True)
            thread.start()
            mythreadstorage[item.item['path']] = thread
            global_work_queue.put(PrioritizedItem(item.priority, {'thread': thread, 'event': event}))
        item.item['thread'] = mythreadstorage[item.item['path']]
        global_request_queue.task_done()


def worker2():
    while True:
        item = global_work_queue.get().item
        item['event'].set()
        item['thread'].join()
        global_work_queue.task_done()




def handleImage(path):
    priority_part = 0 if path.split('/')[-5]==str(global_priority) else 2
    overview_part = 1 if path.startswith('overview') else 0
    workload = {'path': path}
    global_request_queue.put(PrioritizedItem(priority_part + overview_part, workload))
    call_to_do = int(path[:-4].split('/')[-1])
    path_next = '/'.join(path.split('/')[:-1]) + '/' + str(call_to_do + 1) + '.png'
    global_request_queue.put(PrioritizedItem(4 + priority_part, {'path': path_next}))
    global_request_queue.join()
    workload['thread'].join()
    return send_file('tempdata' + os.sep + path.replace('/', os.sep))

@app.route('/battykoda/<path:path>', methods=['POST', 'GET'])
def static_cont(path):
    global threshold

    if path.startswith('img/'):
        return handleImage(path)
    if path.startswith('overview/'):
        return handleImage(path)

    if path.startswith('audio/'):
        return handleSound(path)
    if path.startswith('thres/'):
        return send_from_directory('/'.join(lookup[path[4:]].split(os.sep)[:-1]), path[4:])
    if path.endswith('.jpg'):
        return send_from_directory(osfolder, path.split('/')[-1])

    if os.path.isdir(osfolder + path):
        list_of_files=os.listdir(osfolder + path)
        list_of_files.sort()
        collectFiles=''
        for item in list_of_files:
            if item.endswith('.pickle') or item.endswith('DS_Store'):
                continue
            collectFiles+='<li><a href="'+item+'/">'+item+'</a></li>'

        return render_template('listBK.html', data={'listicle': Markup(collectFiles)})

    if path.startswith('back/'):
        return index(osfolder + path[5:-1], path[5:], request.method == 'POST', undo = True)
    if exists(osfolder + path[:-1] + '.pickle'):
        return index(osfolder + path[:-1], path, request.method == 'POST')
    if request.method == 'POST':
        result = request.form
        threshold = float(result['threshold_nb'])
        if result['threshold'] == 'correct':
            storage = np.array([threshold])

            audiodata, fs = DataReader.data_read(osfolder + path[:-1])
            smoodAudio = thresholding.SmoothData(audiodata, fs)

            onsets, offsets = thresholding.SegmentNotes(smoodAudio, fs, threshold)

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
    audiodata = audiodata[:,0]
    smoodAudio = thresholding.SmoothData(audiodata, fs)

    listims = []
    boink = []
    plttitle = ['start', 'middle', 'end']
    segLen = 100000
    for idx in range(3):
        tf = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        plt.figure(figsize=(3, 3))
        if idx == 0:
            boink = idx
        if idx == 1:
            boink = audiodata.shape[0] // 2
        if idx == 2:
            boink = audiodata.shape[0] - 2 * segLen
        plt.plot(smoodAudio[0 + boink:segLen + boink])
        plt.hlines(threshold, 0, segLen, 'k')
        plt.title(plttitle[idx])
        plt.savefig(tf)
        shorty = tf.name.split(os.sep)[-1]
        lookup[shorty] = tf.name
        listims.append('/battykoda/thres/' + shorty)
        tf.close()

    return render_template('setThreshold.html',
                           data={'images': listims,
                                 'threshold': str(threshold)})

@app.route('/')
def mainpage():
    return render_template('welcometoBK.html', data=dict())


if __name__ == '__main__':

    #from werkzeug.middleware.profiler import ProfilerMiddleware
    #app.wsgi_app = ProfilerMiddleware(app.wsgi_app)
    threading.Thread(target=worker, daemon=True).start()
    threading.Thread(target=worker2, daemon=True).start()
    app.run(host='0.0.0.0', debug=False, port=8060)
