import tables
tables.file._open_files.close_all()
from flask import Flask, render_template, request, url_for, redirect
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

app = Flask(__name__)

global_limit_confidence = 100
global_user_name = ""
global_myfile=h5py.File('/Users/angelessalles/Documents/GitHub/battykoda/templates/Users/Angie/Experiment/Date/Pair_Trial1_1638.mat', 'r')
def store_task(result):
    app.logger.info(result['type_call'])
    app.logger.info('stored!')


def get_task(limit_confidence):
    ch2use=0
    fs=250_000
    halfwin=30

    thrX1=np.argmax(global_myfile['sig'][ch2use,:])
    f, t, Sxx = scipy.signal.spectrogram(global_myfile['sig'][ch2use,thrX1-fs//1000*halfwin:thrX1+fs//1000*halfwin],fs,nperseg=2**8,noverlap=220,nfft=2**8)
              #Sxx[Sxx>1E-7]=1E-7
    plt.pcolormesh(t, f, np.arctan(1E8*Sxx), shading='auto')
    plt.ylabel('Frequency [Hz]')
    plt.xlabel('Time [sec]')
    plt.savefig('static/temp_spect.png')
    
    data = {'spectrogram':'static/temp_spect.png',
            'guess':['FMB','Echo','U'][random.randint(0,2)],
            'confidence':str(random.randint(0,100)),
            'limit_confidence':str(limit_confidence)
            }
    return data


@app.route('/result', methods = ['POST','GET'])


@app.route('/static/<path:path>')
def static_cont(path):
    return send_from_directory('static', path)

@app.route('/', methods = ['POST','GET'])
def index():
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
    data = get_task(global_limit_confidence)
    data['user_name'] = global_user_name
    return render_template('AngieBK.html', data=data)

if __name__ == '__main__':
  app.run(host='0.0.0.0',debug=True, port=8060)