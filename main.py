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
import h5py
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
fs = 250_000


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


def get_task(limit_confidence, path_to_file):
    ch2use = 0

    pfile = open(path_to_file + '.pickle', 'rb')
    segmentData=pickle.load(pfile)
    pfile.close()

    hwin = 3 #ms before and after call
    datafile = h5py.File(path_to_file)

    call_to_do=len(segmentData['labels'])
    onset=(segmentData['onsets'][call_to_do]*fs).astype(int)
    offset=(segmentData['offsets'][call_to_do]*fs).astype(int)

    thrX1 = datafile['ni_data']['mic_data'][ch2use, onset-(fs*hwin//1000):offset+(fs*hwin//1000)]
    f, t, Sxx = scipy.signal.spectrogram(thrX1, fs, nperseg=2**8, noverlap=220, nfft=2**8)
    plt.pcolormesh(t, f, np.arctan(1E8*Sxx), shading='auto')
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
            'limit_confidence': str(limit_confidence)
            }
    return data


def index(path_to_file,path, is_post):
    global global_user_name
    global global_limit_confidence
    if not is_post:
        data = get_task(global_limit_confidence, path_to_file)
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
    store_task(path_to_file,result)
    return redirect(path)



@app.route('/battykoda/<path:path>', methods=['POST', 'GET'])
def static_cont(path):
    ch2use = 0
    global threshold
    if path[-5:] == '.mat/':
        if exists(osfolder + path[:-1] + '.pickle'):
            return index(osfolder + path[:-1], path, request.method == 'POST')
        if request.method == 'POST':
            result = request.form
            if result['threshold'] == 'change':
                threshold = float(result['threshold_nb'])
            else:
                storage = np.array([threshold])


                datafile = h5py.File(osfolder + path[:-1])
                smoodAudio = thresholding.SmoothData(np.array(datafile['ni_data']['mic_data']).flatten(), fs)

                onsets,offsets=thresholding.SegmentNotes(smoodAudio,fs,threshold)

                f=open(osfolder + path[:-1] + '.pickle','wb')
                pickle.dump({'threshold':threshold,
                             'onsets':onsets,
                             'offsets':offsets,
                             'labels':[],
                             'startFrq':[],
                             'endFrq':[]},f)
                f.close()

                return index(osfolder + path[:-1],path, False)

        datafile = h5py.File(osfolder + path[:-1])
        smoodAudio=thresholding.SmoothData(np.array(datafile['ni_data']['mic_data']).flatten(),fs)
        
        listims = []
        boink = []
        plttitle = ['start', 'middle', 'end']
        segLen=100000
        for idx in range(3):
            tf = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            plt.figure(figsize=(3, 3))
            if idx == 0:
                boink = idx
            if idx == 1:
                boink = datafile['ni_data']['mic_data'].shape[1]//2
            if idx == 2:
                boink = datafile['ni_data']['mic_data'].shape[1]-2*segLen
            plt.plot(smoodAudio[0+boink:segLen+boink])
            plt.hlines(threshold, 0, segLen, 'k')
            plt.title(plttitle[idx])
            plt.savefig(tf)
            shorty = tf.name.split(os.sep)[-1]
            lookup[shorty] = tf.name
            listims.append('/battykoda/img/'+shorty)
            tf.close()
        return render_template('setThreshold.html',
                               data={'images': listims,
                                     'threshold': str(threshold)})
    if path[:4] == 'img/':
        return send_from_directory('/'.join(lookup[path[4:]].split(os.sep)[:-1]), path[4:])
    if path[-4:] == '.jpg':
        return send_from_directory(osfolder, path.split('/')[-1])

    return render_template('listBK.html',
                           data={'listicle': Markup(''.join(['<li><a href="'+item+'/">'+item+'</a></li>' for item in os.listdir((osfolder+path))]))})


@app.route('/')
def mainpage():
    return render_template('welcometoBK.html', data=dict())


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=8060)
