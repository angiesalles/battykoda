import pickle
from flask import render_template
from markupsafe import Markup
import htmlGenerator as hG
import GetAudioBit
import os
import urllib.parse
import random
import numpy as np
import subprocess

R = False

def get_task(path_to_file, path, user_setting, osfolder, undo=False):
    # Import all required modules at the function level to avoid scoping issues
    import os
    import urllib.parse
    import numpy as np
    import random
    import htmlGenerator as hG
    import GetAudioBit
    import utils
    from flask import render_template
    from markupsafe import Markup
    
    try:
        with open(path_to_file + '.pickle', 'rb') as pfile:
            segment_data = pickle.load(pfile)
        call_to_do = len(segment_data['labels'])
    except (FileNotFoundError, IOError) as e:
        # Return a user-friendly error message (imports already done at function level)
        # Get the path components to show a more helpful message
        path_parts = path.strip('/').split('/')
        username = path_parts[1] if len(path_parts) > 1 else ""
        species = path_parts[2] if len(path_parts) > 2 else ""
        wav_file = path_parts[-1] if len(path_parts) > 3 else ""
        
        # Create a contextual error message
        if wav_file.lower().endswith('.wav'):
            error_title = "Error: Missing Pickle File"
            error_desc = f"Could not find the pickle file for this WAV file: <code>{path_to_file}.pickle</code>"
            error_reason = """
            <p>This typically occurs when:</p>
            <ul>
                <li>The WAV file doesn't have an associated pickle file with call data</li>
                <li>The pickle file needs to be created first</li>
            </ul>
            <p>For a WAV file to be analyzed, it needs a corresponding pickle file that defines call starts, stops, and labels.</p>
            """
        else:
            error_title = "Error: Invalid Path"
            error_desc = f"The path <code>{path}</code> doesn't lead to a valid file or directory"
            error_reason = """
            <p>This typically occurs when:</p>
            <ul>
                <li>The directory structure is incorrect</li>
                <li>You're trying to access a file that doesn't exist</li>
            </ul>
            """
        
        # Build the complete error message
        error_message = f"""
        <div style="margin: 20px; padding: 15px; background-color: #f8d7da; border-left: 5px solid #dc3545; border-radius: 3px;">
            <h3 style="color: #721c24;">{error_title}</h3>
            <p>{error_desc}</p>
            {error_reason}
            <p>
                <a href="/battykoda/home/" style="color: #0066cc;">Return to Home Directory</a> | 
                <a href="/battykoda/home/{username}/" style="color: #0066cc;">Return to User Directory</a>
                {f' | <a href="/battykoda/home/{username}/{species}/" style="color: #0066cc;">Return to Species Directory</a>' if species else ''}
            </p>
        </div>
        """
        return render_template('listBK.html', data={'listicle': Markup(error_message)})
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
    
    # Process path for audio access
    mod_path = os.sep.join(path.split('/')[:-1])
    mod_path = utils.convert_path_to_os_specific(mod_path)
    audio_path = osfolder + mod_path
    thr_x1, _, hashof = GetAudioBit.get_audio_bit(audio_path, call_to_do, 0)
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
    
    # For each other channel, create HTML with debug image filter
    other_html = []
    for other in others:
        img_src = spectr_particle_fun(other, _overview=False)
        audio_src = audio_particle_fun(other, _overview=False)
        
        # Add each image with debug handling
        other_html.append(f"""
        <p>
          <div class="image-container" style="position: relative; display: inline-block;">
            <img src="{img_src}" width="600" height="250" 
              onerror="this.onerror=null; this.src='/static/broken_image.png'; this.style.border='2px solid red'; this.parentNode.classList.add('broken-image'); console.log('Broken image: {img_src}');" />
            <div class="debug-info" style="display: none; position: absolute; top: 0; left: 0; background: rgba(255,0,0,0.7); color: white; padding: 2px; font-size: 10px;">
                Path: {img_src}
            </div>
          </div>
          <audio controls src="{audio_src}" preload="none">
            Your browser does not support the audio element.
          </audio>
        </p>
        """)
    # We have all required imports at the function start
    
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
