import numpy as np
from scipy.io import wavfile
import time
import hashlib
import os
import logging

# Set up logging
logger = logging.getLogger('battykoda.datareader')

# Explicitly avoid importing h5py as it's not needed and causes issues

class DataReader:
    cache = dict()
    
    @classmethod
    def data_read(cls, path_to_file):
        """
        Read audio data from a file, with improved error handling.
        
        Args:
            path_to_file: Path to the audio file to read
            
        Returns:
            tuple: (audiodata, sample_rate, hash_of_file)
        """
        logger.info(f"Reading audio file: {path_to_file}")
        
        # Check if file exists
        if not os.path.exists(path_to_file):
            logger.error(f"File not found: {path_to_file}")
            raise FileNotFoundError(f"File not found: {path_to_file}")
            
        # Check file size
        file_size = os.path.getsize(path_to_file)
        if file_size == 0:
            logger.error(f"File is empty: {path_to_file}")
            raise ValueError(f"File is empty: {path_to_file}")
            
        # Check if we have a valid cached version
        if path_to_file in cls.cache and time.time() - cls.cache[path_to_file]['time'] < 300:
            logger.debug(f"Using cached audio data for: {path_to_file}")
            fs = cls.cache[path_to_file]['fs']
            audiodata = cls.cache[path_to_file]['audiodata']
            hashof = cls.cache[path_to_file]['hashof']
        else:
            logger.debug(f"Reading new audio data for: {path_to_file}")
            try:
                # Calculate file hash
                with open(path_to_file, 'rb') as f:
                    hashof = hashlib.md5(f.read()).hexdigest()
                
                # Read WAV file
                logger.debug(f"Reading WAV file")
                fs, audiodata = wavfile.read(path_to_file)
                
                # Validate audio data
                if audiodata is None or audiodata.size == 0:
                    logger.error(f"No audio data found in file: {path_to_file}")
                    raise ValueError(f"No audio data found in file: {path_to_file}")
                
                # Handle mono files by converting to stereo
                if len(audiodata.shape) == 1:
                    logger.debug(f"Converting mono audio to stereo (shape before: {audiodata.shape})")
                    audiodata = audiodata.reshape([-1, 1]).repeat(3, axis=1)
                    logger.debug(f"New shape: {audiodata.shape}")
                
                # Normalize audio data
                audiodata = audiodata.astype(float)
                std = np.std(audiodata)
                if std > 0:
                    audiodata /= std
                else:
                    logger.warning(f"Audio data has zero standard deviation (silent file): {path_to_file}")
                
                # Cache the results
                cls.cache[path_to_file] = {
                    'time': time.time(),
                    'fs': fs,
                    'audiodata': audiodata,
                    'hashof': hashof
                }
                
                logger.info(f"Successfully read audio file: {path_to_file} (shape: {audiodata.shape}, fs: {fs})")
                
            except Exception as e:
                logger.error(f"Error reading audio file {path_to_file}: {str(e)}")
                raise
        
        return audiodata, fs, hashof

