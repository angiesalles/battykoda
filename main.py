import os
import tempfile
import tables
tables.file._open_files.close_all()
from flask import Flask, render_template, request, url_for, redirect, Markup, send_from_directory
from PIL import Image
import numpy as np
import random
import sys
import logging
import h5py
import matplotlib
# Force matplotlib to not use any Xwindows backend.
matplotlib.use('Agg')#https://stackoverflow.com/questions/2801882/generating-a-png-with-matplotlib-when-display-is-undefined

import matplotlib.pyplot as plt
import scipy.signal
from os.path import exists

threshold = 0.01

app = Flask(__name__)
osfolder = 'C:/Users/Kevin/Documents/repos/capybara/data/'
computer=os.uname()
if computer.sysname=='Darwin':
    osfolder = '/Users/angelessalles/Documents/data/'
global_limit_confidence = 100
global_user_name = ""
lookup = dict()
def store_task(result):
    app.logger.info(result['type_call'])
    app.logger.info('stored!')


def get_task(limit_confidence,path_to_file):
    ch2use=0
    fs=250_000
    halfwin=30
    datafile = h5py.File(path_to_file)
    thrX1=np.argmax(datafile['ni_data']['mic_data'][ch2use,:])
    f, t, Sxx = scipy.signal.spectrogram(datafile['ni_data']['mic_data'][ch2use,thrX1-fs//1000*halfwin:thrX1+fs//1000*halfwin],fs,nperseg=2**8,noverlap=220,nfft=2**8)
              #Sxx[Sxx>1E-7]=1E-7
    plt.pcolormesh(t, f, np.arctan(1E8*Sxx), shading='auto')
    plt.ylabel('Frequency [Hz]')
    plt.xlabel('Time [sec]')
    tf = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    plt.savefig(tf)
    shorty = tf.name.split('/')[-1]
    lookup[shorty] = tf.name
    tf.close()
    
    data = {'spectrogram':'/battykoda/img/' + shorty,
            'guess':['FMB','Echo','U'][random.randint(0,2)],
            'confidence':str(random.randint(0,100)),
            'limit_confidence':str(limit_confidence)
            }
    return data

def index(path_to_file):
    global global_user_name
    global global_limit_confidence
    if request.method == 'POST':
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
        store_task(result)
        return redirect(url_for('index'))
    data = get_task(global_limit_confidence,path_to_file)
    data['user_name'] = global_user_name
    return render_template('AngieBK.html', data=data)




@app.route('/battykoda/<path:path>', methods = ['POST','GET'])
def static_cont(path):
    ch2use = 0
    global threshold
    if request.method == 'POST':
        result = request.form
        if result['threshold'] == 'change':
            threshold = float(result['threshold_nb'])
        else:
            storage = np.array([threshold])
            np.save(osfolder + path[:-1] + '.npy', storage)

    if path[-5:] == '.mat/':
        if exists(osfolder + path[:-1] + '.npy'):
           return index(osfolder + path[:-1])
        datafile = h5py.File(osfolder + path[:-1])
        listims = []
        boink = []
        plttitle = ['start', 'middle', 'end']
        for idx in range(3):
            tf = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            plt.figure(figsize=(3,3))
            if idx == 0:
                boink = idx
            if idx == 1:
                boink = datafile['ni_data']['mic_data'].shape[1]//2
            if idx == 2:
                boink = datafile['ni_data']['mic_data'].shape[1]-2000
            plt.plot(datafile['ni_data']['mic_data'][ch2use, 0+boink:1000+boink])
            plt.hlines(threshold,0,1000,'k')
            plt.title(plttitle[idx])
            plt.savefig(tf)
            shorty = tf.name.split('/')[-1]
            lookup[shorty] = tf.name
            listims.append('/battykoda/img/'+shorty)
            tf.close()
        return render_template('setThreshold.html',
                               data={'images':listims,
                                     'threshold':str(threshold)})
    if path[:4] == 'img/':
        return send_from_directory('/'.join(lookup[path[4:]].split('/')[:-1]), path[4:])

    return render_template('listBK.html',
                           data={'listicle':Markup(''.join(['<li><a href="'+item+'/">'+item+'</a></li>' for item in os.listdir((osfolder+path))]))})

@app.route('/')
def mainpage():
    return render_template('welcometoBK.html', data=dict())



if __name__ == '__main__':
  app.run(host='0.0.0.0',debug=True, port=8060)