import os
import tempfile
import thresholding
import htmlGenerator as hG
from flask import Flask, render_template, request, url_for, redirect, Markup, send_from_directory
import pickle
import numpy as np
import random
import matplotlib.pyplot as plt
import scipy.signal
from os.path import exists
import DataReader
import matplotlib
import platform
import time

# Force matplotlib to not use any Xwindows backend.
# https://stackoverflow.com/questions/2801882/generating-a-png-with-matplotlib-when-display-is-undefined
matplotlib.use('Agg')

threshold = 0.01

app = Flask(__name__)
osfolder = '/Users/angelessalles/Documents/data/'
computer = platform.uname()
if computer.system == 'Windows':
    osfolder = 'C:/Users/Kevin/Documents/repos/capybara/data/'
global_limit_confidence = 100
global_user_name = ""
lookup = dict()
global_contrast = 4



def store_task(path_to_file,result):

    pfile = open(path_to_file + '.pickle', 'rb')
    segmentData=pickle.load(pfile)
    pfile.close()
    pfile = open(path_to_file+'.pickle', 'wb')
    pickle.dump({'threshold': segmentData['threshold'],
                 'onsets': segmentData['onsets'],
                 'offsets': segmentData['offsets'],
                 'labels': segmentData['labels']+[result],
                 'startFrq': [],
                 'endFrq': []}, pfile)
    pfile.close()


def get_task(limit_confidence, contrast, path_to_file):


    pfile = open(path_to_file + '.pickle', 'rb')
    segmentData=pickle.load(pfile)
    pfile.close()

    hwin = 10 #ms before and after call
    audiodata, fs = DataReader.data_read(path_to_file)

    temocontrast = 10**(float(contrast))

    if len(segmentData['labels'])==len(segmentData['offsets']):
        return None
    call_to_do=len(segmentData['labels'])
    onset=(segmentData['onsets'][call_to_do]*fs).astype(int)
    offset=(segmentData['offsets'][call_to_do]*fs).astype(int)

    thrX1 = audiodata[onset-(fs*hwin//1000):offset+(fs*hwin//1000)]
    f, t, Sxx = scipy.signal.spectrogram(thrX1, fs, nperseg=2**8, noverlap=250, nfft=2**8)
    plt.figure()
    plt.pcolormesh(t, f, np.arctan(temocontrast*Sxx), shading='auto')
    plt.ylabel('Frequency [Hz]')
    plt.xlabel('Time [sec]')
    tf = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    plt.savefig(tf)
    shorty = tf.name.split(os.sep)[-1]
    lookup[shorty] = tf.name
    tf.close()
    
    data = {'spectrogram': '/battykoda/img/' + shorty,
            'guess': ['FMB', 'Echo', 'U'][random.randint(0, 2)],
            'confidence': str(random.randint(0, 100)),
            'limit_confidence': str(limit_confidence),
            'currentcall' : call_to_do,
            'totalcalls' : len(segmentData['offsets']),
            'contrast': str(contrast),
            }
    return data


def index(path_to_file,path, is_post):
    global global_user_name
    global global_limit_confidence
    global global_contrast
    if not is_post:
        data = get_task(global_limit_confidence, global_contrast, path_to_file)
        if data==None:
            return render_template('endFile.html',data={'filedirectory':'/battykoda/'+'/'.join(path.split('/')[:-2])+'/'})
        data['user_name'] = global_user_name
        txtsp, jpgsp = hG.spgather(path, osfolder)
        data['species'] = Markup(txtsp)
        data['jpgname'] = jpgsp
        return render_template('AngieBK.html', data=data)
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
    store_task(path_to_file,result)
    return index(path_to_file, path, False)



@app.route('/battykoda/<path:path>', methods=['POST', 'GET'])
def static_cont(path):
    ch2use = 0
    global threshold

    if path[:4] == 'img/':
        return send_from_directory('/'.join(lookup[path[4:]].split(os.sep)[:-1]), path[4:])
    if path[-4:] == '.jpg':
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

    audiodata, fs = DataReader.data_read(osfolder + path[:-1])
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
        listims.append('/battykoda/img/' + shorty)
        tf.close()
    return render_template('setThreshold.html',
                           data={'images': listims,
                                 'threshold': str(threshold)})

@app.route('/')
def mainpage():
    return render_template('welcometoBK.html', data=dict())


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=8060)
