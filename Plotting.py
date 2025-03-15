import matplotlib.pyplot as plt
import matplotlib
import GetAudioBit
import os
import scipy.signal
import numpy as np
import SoftCreateFolders
from AppropriateFile import appropriate_file
import Hwin
import logging
import traceback
import tempfile
import shutil

# Set up logging
logger = logging.getLogger('battykoda.plotting')

# Force matplotlib to not use any Xwindows backend.
# https://stackoverflow.com/questions/2801882/generating-a-png-with-matplotlib-when-display-is-undefined
matplotlib.use('Agg')

def plotting(path, args, event, osfolder):
    logger.info(f"Starting plotting for path: {path}")
    file_path = None
    
    try:
        event.wait()
        
        # Get the paths we need to work with early, so we can log errors properly
        folder_path = appropriate_file(path, args, osfolder, folder_only=True)
        file_path = appropriate_file(path, args, osfolder)
        
        # Log debugging info for temp files
        logger.info(f"Generating spectrogram image:")
        logger.debug(f"  - Folder: {folder_path}")
        logger.debug(f"  - File: {file_path}")
        
        # Ensure directory exists first
        if not SoftCreateFolders.soft_create_folders(folder_path):
            logger.error(f"Failed to create directory: {folder_path}")
            return

        # Getting audio data
        logger.info(f"Getting audio data for path: {osfolder + os.sep.join(path.split('/')[:-1])}")
        
        try:
            overview = args['overview'] == 'True'
            hwin = Hwin.overview_hwin if overview else Hwin.normal_hwin
            call_to_do = int(args['call'])
            contrast = float(args['contrast'])
            
            audio_path = osfolder + os.sep.join(path.split('/')[:-1])
            logger.debug(f"Audio file path: {audio_path}")
            
            thr_x1, fs, hashof = GetAudioBit.get_audio_bit(audio_path, call_to_do, hwin)
            logger.debug(f"Audio data loaded: fs={fs}, hash={hashof}")
            
            # Validate audio data
            if thr_x1 is None or thr_x1.size == 0:
                logger.error(f"Audio data is empty or None")
                return
                
            errorc = fs < 0
            fs = np.abs(fs)
            
            # Check channel is valid
            if int(args['channel']) >= thr_x1.shape[1]:
                logger.error(f"Channel index {args['channel']} is out of bounds for array of shape {thr_x1.shape}")
                return
                
            thr_x1 = thr_x1[:, int(args['channel'])]
            
            # Verify hash matches
            if args['hash'] != hashof:
                logger.error(f"Hash mismatch: {args['hash']} vs {hashof}")
                return
                
            # Generate spectrogram
            logger.debug("Generating spectrogram")
            f, t, sxx = scipy.signal.spectrogram(thr_x1, fs, nperseg=2 ** 8, noverlap=254, nfft=2 ** 8)
            
            # Create figure
            plt.figure(figsize=(8, 6), facecolor='black')
            ax = plt.axes()
            ax.set_facecolor('indigo')
            temocontrast = 10 ** contrast
            plt.pcolormesh(t, f, np.arctan(temocontrast * sxx), shading='auto')
            
            if not overview:
                plt.xlim(0, 0.050)
                
            ax.tick_params(axis='x', colors='white')
            ax.tick_params(axis='y', colors='white')
            ax.xaxis.label.set_color('white')
            ax.yaxis.label.set_color('white')
            
            if errorc:
                plt.ylabel('kevinerror')
                plt.xlabel('kevinerror')
            else:
                plt.ylabel('Frequency [Hz]')
                plt.xlabel('Time [sec]')
            
            # Save to a temporary file first, then move it to final destination
            # This helps avoid partial writes
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            temp_file.close()
            
            logger.debug(f"Saving figure to temp file: {temp_file.name}")
            plt.savefig(temp_file.name, dpi=100)
            plt.close()
            
            # Check if temp file was created successfully
            if os.path.exists(temp_file.name) and os.path.getsize(temp_file.name) > 0:
                # Move the file to the final destination
                logger.debug(f"Moving temp file to: {file_path}")
                shutil.move(temp_file.name, file_path)
                
                # Double-check the file exists and has content
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    logger.info(f"Successfully created: {file_path}")
                else:
                    logger.error(f"ERROR: Final file not created properly: {file_path}")
            else:
                logger.error(f"ERROR: Temp file not created properly: {temp_file.name}")
                if os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)
                    
        except AssertionError as e:
            logger.error(f"Assertion error in plotting: {str(e)}")
            logger.debug(traceback.format_exc())
            plt.close()  # Make sure to close the figure even on error
            
        except Exception as e:
            logger.error(f"Error in audio processing or plotting: {str(e)}")
            logger.debug(traceback.format_exc())
            plt.close()  # Make sure to close the figure even on error
            
    except Exception as e:
        logger.error(f"Unexpected error in plotting: {str(e)}")
        logger.debug(traceback.format_exc())
        
        if file_path:
            # Try to create an error image that explains the problem
            try:
                fig = plt.figure(figsize=(8, 6), facecolor='red')
                ax = plt.axes()
                ax.text(0.5, 0.5, f"Error: {str(e)}", 
                        horizontalalignment='center',
                        verticalalignment='center',
                        transform=ax.transAxes,
                        color='white',
                        fontsize=14)
                ax.set_axis_off()
                
                # Make sure directory exists
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                plt.savefig(file_path)
                plt.close()
                logger.info(f"Created error image: {file_path}")
            except Exception as e2:
                logger.error(f"Failed to create error image: {str(e2)}")
                plt.close()

