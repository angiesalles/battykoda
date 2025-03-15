import pickle
import urllib
import GetAudioBit
import os
from flask import render_template
from markupsafe import Markup


def get_listing(path_to_file, osfolder, path):
    pickle_path = os.sep + os.sep.join(path_to_file.split('/')[:-1]) + '.pickle'
    try:
        with open(pickle_path, 'rb') as pfile:
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
                         
        return render_template('classification_review.html', data={'title': path_to_file.split('/')[-1][:-12],
                                                          'output': Markup(collector)})
                                                          
    except (FileNotFoundError, IOError) as e:
        # Return a user-friendly error message
        # Get the path components to show a more helpful message
        path_parts = path.strip('/').split('/')
        username = path_parts[1] if len(path_parts) > 1 else ""
        species = path_parts[2] if len(path_parts) > 2 else ""
        
        # Build the complete error message
        error_message = f"""
        <div style="margin: 20px; padding: 15px; background-color: #f8d7da; border-left: 5px solid #dc3545; border-radius: 3px;">
            <h3 style="color: #721c24;">Error: Pickle File Not Found</h3>
            <p>Could not find the required pickle file: <code>{pickle_path}</code></p>
            <p>This error occurs when:</p>
            <ul>
                <li>The file doesn't exist at the specified location</li>
                <li>The pickle file needs to be created first</li>
                <li>You may be trying to navigate to a folder that doesn't contain call data</li>
            </ul>
            <p>
                <a href="/battycoda/home/" style="color: #0066cc;">Return to Home Directory</a> | 
                <a href="/battycoda/home/{username}/" style="color: #0066cc;">Return to User Directory</a>
                {f' | <a href="/battycoda/home/{username}/{species}/" style="color: #0066cc;">Return to Species Directory</a>' if species else ''}
            </p>
        </div>
        """
        return render_template('listBC.html', data={'listicle': Markup(error_message)})