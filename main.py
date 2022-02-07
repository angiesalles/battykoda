from flask import Flask, render_template, request, url_for, redirect
from PIL import Image
import numpy as np
import random
import sys
import logging
app = Flask(__name__)

global_limit_confidence = 100
global_user_name = ""
logging.basicConfig(level=logging.DEBUG)
def store_task(result):
    app.logger.info(result['type_call'])
    app.logger.info('stored!')


def get_task(confidence):
    im = Image.fromarray(np.random.random_integers(low=0,high=255,size=(200,200)).astype(np.uint8))
    im.save('static/12345.png')
    im = Image.fromarray(np.random.random_integers(low=0, high=120, size=(100, 100)).astype(np.uint8))
    im.save('static/67890.png')
    data = {'spectrogram':'static/12345.png',
            'waveform':'static/67890.png',
            'guess':['FMB','Echo','U'][random.randint(0,2)],
            'confidence':str(random.randint(0,100)),
            'limit_confidence':str(confidence)
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
    return render_template('myfile.html', data=data)

if __name__ == '__main__':
   app.run(debug = True)