import pickle
import urllib
import GetAudioBit
import os
from flask import render_template, Markup
import numpy as np
import numpy
def get_listing(path_to_file, osfolder, path):
    with open(os.sep + os.sep.join(path_to_file.split('/')[:-1]) + '.pickle', 'rb') as pfile:
        segment_data = pickle.load(pfile)
        collector = ''
        counter = 0
        for idx in range(len(segment_data['labels'])):
            if not segment_data['labels'][idx]['type_call'] == path_to_file.split('/')[-1][:-12]:
                continue
            thr_x1, _, hashof = GetAudioBit.get_audio_bit(osfolder + os.sep.join(path.split('/')[:-1]), idx, 0)

            def spectr_particle_fun(_channel, _overview):

                args = {'hash': hashof,
                        'call': idx,
                        'channel': _channel,
                        'overview': _overview,
                        'contrast': 1,
                        'numcalls': len(segment_data['offsets'])}
                return '/img/' + path_to_file + 'spectrogram.png?' + urllib.parse.urlencode(args)

            if counter % 3 == 0 and counter > 0:
                collector += '</tr><tr>'
            counter += 1
            particle = 'call_' + str(idx)
            collector += "<td><img width=400 height=300 src='" \
                         + spectr_particle_fun(1, False) \
                         + "' /><br /><center><input type='checkbox' id='"\
                         + particle \
                         + "' name='"\
                         + particle\
                         + "' value='"\
                         + particle\
                         + "'><br /></td>"
        return render_template('AngieBK_review.html', data={'title': path_to_file.split('/')[-1][:-12],
                                                            'output':Markup(collector)})
