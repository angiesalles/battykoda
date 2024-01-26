import pickle
from flask import render_template, Markup
import htmlGenerator as hG
import GetAudioBit
import os
import urllib.parse
import random
import numpy as np
import subprocess

R = False

def get_task(path_to_file, path, user_setting, osfolder, undo=False):
    with open(path_to_file + '.pickle', 'rb') as pfile:
        segment_data = pickle.load(pfile)
    call_to_do = len(segment_data['labels'])
    if undo:
        popped = segment_data['labels'].pop()
        assumed_answer = popped['type_call']
        with open(path_to_file + '.pickle', 'wb') as pfile:
            pickle.dump(segment_data, pfile)
        confidence = -1
    else:
        if R:
            returnvalue = subprocess.run("/usr/bin/Rscript --vanilla Forwardpass.R "
                                          + osfolder
                                          + os.sep.join(path.split('/')[:-1])
                                          + ' '
                                          + str(segment_data['onsets'][call_to_do])
                                          + ' '
                                          + str(segment_data['offsets'][call_to_do]), shell=True,  capture_output=True)
            assumed_answer = returnvalue.stdout.splitlines()[-3][4:].decode()
            confidence = float(returnvalue.stdout.splitlines()[-1][4:])
        else:
            assumed_answer = 'Echo'
            confidence = 50.0
    if call_to_do == len(segment_data['offsets']):
        return render_template('endFile.html',
                               data={'filedirectory': '/battykoda/' + '/'.join(path.split('/')[:-2]) + '/'})
    backfragment = ''
    if call_to_do > 0:
        backfragment = Markup('<a href="/battykoda/back/'+path+'">Undo</a>')
    txtsp, jpgsp = hG.spgather(path, osfolder, assumed_answer)
    thr_x1, _, hashof = GetAudioBit.get_audio_bit(osfolder + os.sep.join(path.split('/')[:-1]), call_to_do, 0)
    idx_main = min(int(user_setting['main']), thr_x1.shape[1])-1

    def spectr_particle_fun(_channel, _overview):
        args = {'hash': hashof,
                'call': call_to_do,
                'channel': _channel,
                'overview': _overview,
                'contrast': user_setting['contrast'],
                'numcalls': len(segment_data['offsets'])}
        return '/img/' + path + 'spectrogram.png?' + urllib.parse.urlencode(args)

    def audio_particle_fun(_channel, _overview):
        args = {'hash': hashof,
                'channel': _channel,
                'call': call_to_do,
                'overview': _overview,
                'loudness': user_setting['loudness']}
        return '/audio/' + path + 'snippet.wav?' + urllib.parse.urlencode(args)
    others = np.setdiff1d(range(thr_x1.shape[1]), idx_main)
    other_html = ['<p><img src="'+spectr_particle_fun(other, _overview=False)+'" width="600" height="250" >' +
                  '<audio controls src="' + audio_particle_fun(other, _overview=False) + '" preload="none" />' +
                  '</p>' for other in others]
    data = {'spectrogram': spectr_particle_fun(idx_main, _overview=False),
            'spectrogram_large': spectr_particle_fun(idx_main, _overview=True),
            'confidence': confidence,
            'currentcall': call_to_do,
            'totalcalls': len(segment_data['offsets']),
            'backlink': backfragment,
            'audiolink': audio_particle_fun(idx_main, _overview=False),
            'long_audiolink': audio_particle_fun(idx_main, _overview=True),
            'species': Markup(txtsp),
            'jpgname': jpgsp,
            'focused': assumed_answer,
            'main': idx_main+1,
            'max_main': thr_x1.shape[1],
            'others': Markup(''.join(other_html)),
            }
    return render_template('AngieBK.html', data={**user_setting, **data})
