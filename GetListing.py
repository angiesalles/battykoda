import pickle
import urllib
import GetAudioBit
import os
from flask import render_template, Markup
def get_listing(path_to_file, osfolder, path):
    with open(path_to_file + '.pickle', 'rb') as pfile:
        segment_data = pickle.load(pfile)
        collector = ''


        for idx in range(len(segment_data)):
            thr_x1, _, hashof = GetAudioBit.get_audio_bit(osfolder + os.sep.join(path.split('/')[:-1]), idx, 0)

            def spectr_particle_fun(_channel, _overview):

                args = {'hash': hashof,
                        'call': idx,
                        'channel': _channel,
                        'overview': _overview,
                        'contrast': 1,
                        'numcalls': len(segment_data['offsets'])}
                return '/img/' + path_to_file + 'spectrogram.png?' + urllib.parse.urlencode(args)
            collector+=segment_data.label[idx]+ "<img src='" + spectr_particle_fun(1,False) + "' />"
        return render_template('AngieBK_review.html', data={'output':Markup(collector)})
