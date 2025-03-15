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
import logging
import re

# Set up logging
logger = logging.getLogger('battykoda.gettask')

# R is installed now, so set to True
R = True

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
            try:
                # Get the species from the path
                path_parts = path.strip('/').split('/')
                species = path_parts[2] if len(path_parts) > 2 else "Efuscus"
                
                # Use the new classify_call.R script
                r_script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "classify_call.R")
                
                # Get the full path to the WAV file
                wav_file_path = os.path.join(osfolder + os.sep.join(path.split('/')[:-1]), path.split('/')[-1])
                
                # Log the command details
                cmd = [
                    "Rscript", 
                    "--vanilla", 
                    r_script_path,
                    wav_file_path,
                    str(segment_data['onsets'][call_to_do]),
                    str(segment_data['offsets'][call_to_do]),
                    species
                ]
                logger.info(f"Running R script: {' '.join(cmd)}")
                
                # Enhanced logging before running R script
                logger.info(f"Running R script with command: {' '.join(cmd)}")
                logger.info(f"Current working directory: {os.getcwd()}")
                
                # Run R script with proper argument handling
                returnvalue = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=False  # Don't raise exception on non-zero exit
                )
                
                # Detailed logging of R script execution
                logger.info(f"R script return code: {returnvalue.returncode}")
                logger.info(f"R script stdout: {returnvalue.stdout}")
                
                if returnvalue.stderr:
                    logger.error(f"R script stderr: {returnvalue.stderr}")
                
                # Check return code
                if returnvalue.returncode != 0:
                    logger.error(f"R script failed with code {returnvalue.returncode}: {returnvalue.stderr}")
                    assumed_answer = 'Echo'
                    confidence = 50.0
                else:
                    # Parse output from R - the new classify_call.R script outputs in a standardized format
                    stdout_lines = returnvalue.stdout.splitlines()
                    logger.debug(f"R script output lines: {stdout_lines}")
                    
                    # Extract the call type and confidence
                    type_line = None
                    conf_line = None
                    
                    # Log all lines for debugging
                    for i, line in enumerate(stdout_lines):
                        logger.debug(f"Line {i}: {line}")
                    
                    # Look for lines containing call type and confidence values
                    # The new script outputs in a consistent format: "type: 'X'" and "confidence: Y.Z"
                    for line in stdout_lines:
                        if line.strip().startswith("type:"):
                            type_line = line
                            logger.debug(f"Found type line: {line}")
                        elif line.strip().startswith("confidence:"):
                            conf_line = line
                            logger.debug(f"Found confidence line: {line}")
                    
                    if type_line and conf_line:
                        # Extract values using regex with better matching patterns
                        logger.debug(f"Extracting from type_line: {type_line}")
                        logger.debug(f"Extracting from conf_line: {conf_line}")
                        
                        # Match any quoted string for type
                        type_match = re.search(r"type:\s*['\"]([^'\"]+)['\"]", type_line)
                        
                        # Match any number for confidence
                        conf_match = re.search(r"confidence:\s*(\d+\.?\d*)", conf_line)
                        
                        logger.debug(f"Type match: {type_match.groups() if type_match else 'None'}")
                        logger.debug(f"Conf match: {conf_match.groups() if conf_match else 'None'}")
                        
                        if type_match:
                            assumed_answer = type_match.group(1)
                            logger.info(f"Extracted type: {assumed_answer}")
                        else:
                            assumed_answer = 'Echo'
                            logger.warning("Could not extract type, using default 'Echo'")
                            
                        if conf_match:
                            confidence = float(conf_match.group(1))
                            logger.info(f"Extracted confidence: {confidence}")
                        else:
                            confidence = 50.0
                            logger.warning("Could not extract confidence, using default 50.0")
                    else:
                        logger.warning("Could not parse R output correctly")
                        assumed_answer = 'Echo'
                        confidence = 50.0
            except Exception as e:
                logger.error(f"Error running R script: {str(e)}")
                assumed_answer = 'Echo'
                confidence = 50.0
        else:
            # Fallback if R is disabled
            assumed_answer = 'Echo'
            confidence = 50.0
        
        # Make sure confidence is between 0 and 100
        confidence = max(0, min(100, confidence))
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
        
        # Add each image with debug handling - without inline styling
        other_html.append(f"""
        <div class="channel-item">
          <h4>Channel {other+1}</h4>
          <div class="image-container">
            <img src="{img_src}" class="responsive-image"
              onerror="this.onerror=null; this.src='/static/broken_image.png'; this.parentNode.classList.add('broken-image'); console.log('Broken image: {img_src}');" />
            <div class="debug-info">
                Path: {img_src}
            </div>
          </div>
          <audio controls src="{audio_src}" preload="none" class="channel-audio">
            Your browser does not support the audio element.
          </audio>
        </div>
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
