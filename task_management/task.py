"""
Task management functionality for BattyCoda application.
"""
import os
import pickle
import urllib.parse
import random
import numpy as np
import logging
import csv
from flask import render_template
from markupsafe import Markup

import htmlGenerator as hG
import GetAudioBit
import utils
from task_management.audio_processing import run_r_classification

# Set up logging
logger = logging.getLogger('battykoda.task_management.task')

def get_task(path, user_setting, undo=False):
    """
    Main task handler for processing audio files.
    
    Args:
        path (str): Path to the WAV file
        user_setting (dict): User settings
        undo (bool): Whether this is an undo operation
        
    Returns:
        str: Rendered HTML with task information
    """
    try:
        pickle_path = utils.convert_path_to_os_specific(path) + '.pickle'
        logger.info(f"PICKLE DEBUG: Looking for pickle file at {pickle_path}")
        
        # Check if file exists
        if os.path.exists(pickle_path):
            logger.info(f"PICKLE DEBUG: Pickle file exists at {pickle_path}")
        else:
            logger.error(f"PICKLE DEBUG: Pickle file NOT found at {pickle_path}")
            # List files in directory
            dir_path = os.path.dirname(pickle_path)
            if os.path.exists(dir_path):
                logger.info(f"PICKLE DEBUG: Directory exists: {dir_path}")
                files = os.listdir(dir_path)
                logger.info(f"PICKLE DEBUG: Files in directory: {files}")
                pickle_files = [f for f in files if f.endswith('.pickle')]
                logger.info(f"PICKLE DEBUG: Pickle files: {pickle_files}")
            else:
                logger.error(f"PICKLE DEBUG: Directory does not exist: {dir_path}")
        
        # Try to open the file
        with open(pickle_path, 'rb') as pfile:
            logger.info(f"PICKLE DEBUG: Successfully opened pickle file")
            segment_data = pickle.load(pfile)
            logger.info(f"PICKLE DEBUG: Successfully loaded pickle data with {len(segment_data['labels'])} labels")
        call_to_do = len(segment_data['labels'])
    except (FileNotFoundError, IOError) as e:
        logger.error(f"PICKLE DEBUG: Error opening pickle file: {str(e)}")
        # Return a user-friendly error message (imports already done at function level)
        # Get the path components to show a more helpful message
        path_parts = path.strip('/').split('/')
        username = path_parts[1] if len(path_parts) > 1 else ""
        species = path_parts[2] if len(path_parts) > 2 else ""
        wav_file = path_parts[-1] if len(path_parts) > 3 else ""
        
        # Create a contextual error message
        if wav_file.lower().endswith('.wav'):
            error_title = "Error: Missing Pickle File"
            error_desc = f"Could not find the pickle file for this WAV file: <code>{path}.pickle</code>"
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
                <a href="/home/" style="color: #0066cc;">Return to Home Directory</a> | 
                <a href="/home/{username}/" style="color: #0066cc;">Return to User Directory</a>
                {f' | <a href="/home/{username}/{species}/" style="color: #0066cc;">Return to Species Directory</a>' if species else ''}
            </p>
        </div>
        """
        return render_template('listBC.html', data={'listicle': Markup(error_message)})
    
    if undo:
        popped = segment_data['labels'].pop()
        assumed_answer = popped['type_call']
        with open(path + '.pickle', 'wb') as pfile:
            pickle.dump(segment_data, pfile)
        confidence = -1
    else:
        # Get the species from the path
        path_parts = path.strip('/').split('/')
        species = path_parts[2] if len(path_parts) > 2 else "Efuscus"

        # Get the full path to the WAV file
        wav_file_path = utils.convert_path_to_os_specific(path)
        
        # Call the R classification function
        assumed_answer, confidence = run_r_classification(
            wav_file_path,
            segment_data['onsets'][call_to_do],
            segment_data['offsets'][call_to_do],
            species
        )
    
    if call_to_do == len(segment_data['offsets']):
        return render_template('endFile.html',
                               data={'filedirectory': '/' + '/'.join(path.split('/')[:-2]) + '/'})
    
    backfragment = ''
    if call_to_do > 0:
        backfragment = Markup('<a href="/back/'+path+'">Undo</a>')
    
    txtsp, jpgsp = hG.spgather(path, assumed_answer)
    
    # Process path for audio access
    mod_path = utils.convert_path_to_os_specific(path)
    thr_x1, _, hashof = GetAudioBit.get_audio_bit(mod_path, call_to_do, 0)
    idx_main = min(int(user_setting['main']), thr_x1.shape[1])-1

    def spectr_particle_fun(_channel, _overview):
        # Use new API format with wav_path
        args = {'wav_path': path,
                'hash': hashof,
                'call': call_to_do,
                'channel': _channel,
                'overview': '1' if _overview else '0',  # Use numeric values for consistency
                'contrast': user_setting['contrast'],
                'numcalls': len(segment_data['offsets'])}
        return '/spectrogram?' + urllib.parse.urlencode(args)

    def audio_particle_fun(_channel, _overview):
        # Use new API format with wav_path
        args = {'wav_path': path,
                'hash': hashof,
                'channel': _channel,
                'call': call_to_do,
                'overview': '1' if _overview else '0',  # Use numeric values for consistency
                'loudness': user_setting['loudness']}
        return '/audio/snippet?' + urllib.parse.urlencode(args)
        
    others = np.setdiff1d(range(thr_x1.shape[1]), idx_main)
    
    # For each other channel, create HTML with debug image filter
    other_html = []
    for other in others:
        img_src = spectr_particle_fun(other, _overview=False)
        audio_src = audio_particle_fun(other, _overview=False)
        
        # Add each image with clean handling
        other_html.append(f"""
        <div class="channel-item">
          <h4>Channel {other+1}</h4>
          <div class="image-container">
            <img src="{img_src}" class="responsive-image" alt="Channel {other+1} Spectrogram" />
          </div>
          <audio controls src="{audio_src}" preload="none" class="channel-audio">
            Your browser does not support the audio element.
          </audio>
        </div>
        """)
    
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
    return render_template('classification_view.html', data={**user_setting, **data})