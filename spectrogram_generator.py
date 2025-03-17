"""
Pure functions for generating spectrograms.
This module extracts the core plotting functionality into pure, stateless functions.
"""
import os
import tempfile
import shutil
import logging
import traceback
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import scipy.signal
from AppropriateFile import appropriate_file
import GetAudioBit
import Hwin
import SoftCreateFolders

# Configure logging
logger = logging.getLogger('battykoda.spectrogram_generator')

# Force matplotlib to not use any Xwindows backend
matplotlib.use('Agg')

def generate_spectrogram(path, args, output_path=None):
    """
    Pure function to generate a spectrogram.
    
    Args:
        path: Path to the audio file
        args: Dict of parameters (call, channel, etc.)
        output_path: Optional output path, will be generated if not provided
        
    Returns:
        tuple: (success, output_path, error_message)
    """
    if output_path is None:
        output_path = appropriate_file(path, args)
    
    logger.info(f"Generating spectrogram: {output_path}")
    logger.debug(f"Parameters: {args}")
    
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Parse parameters
        call_to_do = int(args.get('call', 0))
        overview = args.get('overview') == '1' or args.get('overview') == 'True'
        channel = int(args.get('channel', 0))
        contrast = float(args.get('contrast', 4))
        
        # Select window size
        hwin = Hwin.overview_hwin if overview else Hwin.normal_hwin
        
        # Get audio data
        logger.debug(f"Getting audio data from: {path}")
        thr_x1, fs, hashof = GetAudioBit.get_audio_bit(path, call_to_do, hwin)
        
        # Validate audio data
        if thr_x1 is None or thr_x1.size == 0:
            logger.error(f"Audio data is empty or None")
            return False, output_path, "Audio data is empty"
            
        # Check channel is valid
        if channel >= thr_x1.shape[1]:
            logger.error(f"Channel index {channel} is out of bounds for array of shape {thr_x1.shape}")
            return False, output_path, f"Channel index {channel} is out of bounds"
            
        # Extract channel
        thr_x1 = thr_x1[:, channel]
        
        # Verify hash matches
        if args.get('hash') != hashof:
            logger.error(f"Hash mismatch: {args.get('hash')} vs {hashof}")
            return False, output_path, "Hash validation failed"
            
        # Generate spectrogram
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
        
        if fs < 0:  # Mark error condition
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
            logger.debug(f"Moving temp file to: {output_path}")
            shutil.move(temp_file.name, output_path)
            
            # Double-check the file exists and has content
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logger.info(f"Successfully created: {output_path}")
                return True, output_path, None
            else:
                logger.error(f"ERROR: Final file not created properly: {output_path}")
                return False, output_path, "Failed to create output file"
        else:
            logger.error(f"ERROR: Temp file not created properly: {temp_file.name}")
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
            return False, output_path, "Failed to create temporary file"
                
    except Exception as e:
        logger.error(f"Error generating spectrogram: {str(e)}")
        logger.debug(traceback.format_exc())
        try:
            plt.close()  # Make sure to close the figure even on error
        except:
            pass
        
        # Try to create an error image
        try:
            create_error_image(output_path, str(e))
            return False, output_path, str(e)
        except:
            return False, output_path, str(e)

def create_error_image(output_path, error_message):
    """
    Create an error image with the given message.
    
    Args:
        output_path: Where to save the image
        error_message: Error message to display
        
    Returns:
        bool: Success status
    """
    try:
        # Create directory if needed
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Create figure
        fig = plt.figure(figsize=(8, 6), facecolor='red')
        ax = plt.axes()
        ax.text(0.5, 0.5, f"Error: {error_message}", 
                horizontalalignment='center',
                verticalalignment='center',
                transform=ax.transAxes,
                color='white',
                fontsize=14)
        ax.set_axis_off()
        
        # Save image
        plt.savefig(output_path)
        plt.close()
        
        return os.path.exists(output_path)
        
    except Exception as e:
        logger.error(f"Failed to create error image: {str(e)}")
        plt.close()
        return False