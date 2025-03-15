import DataReader
import pickle
import os
import logging
import traceback

# Set up logging
logger = logging.getLogger('battykoda.getaudiobit')

def get_audio_bit(path_to_file, call_to_do, hwin):
    """
    Extract a segment of audio data for a specific call.
    
    Args:
        path_to_file: Path to the audio file
        call_to_do: Index of the call to extract
        hwin: Window size in milliseconds
        
    Returns:
        tuple: (audio_segment, sample_rate, hash_of_file)
    """
    try:
        logger.info(f"Getting audio bit for path: {path_to_file}, call: {call_to_do}")
        
        # Check if audio file exists
        if not os.path.exists(path_to_file):
            logger.error(f"Audio file not found: {path_to_file}")
            raise FileNotFoundError(f"Audio file not found: {path_to_file}")
            
        # Check if pickle file exists
        pickle_path = path_to_file + '.pickle'
        if not os.path.exists(pickle_path):
            logger.error(f"Pickle file not found: {pickle_path}")
            raise FileNotFoundError(f"Pickle file not found: {pickle_path}")
        
        # Read audio data
        logger.debug(f"Reading audio data")
        audiodata, fs, hashof = DataReader.DataReader.data_read(path_to_file)
        
        # Load segment data from pickle file
        logger.debug(f"Loading segment data from {pickle_path}")
        try:
            with open(pickle_path, 'rb') as pfile:
                segment_data = pickle.load(pfile)
        except Exception as e:
            logger.error(f"Error loading pickle file {pickle_path}: {str(e)}")
            raise
        
        # Validate segment data
        if 'onsets' not in segment_data or 'offsets' not in segment_data:
            logger.error(f"Invalid segment data: missing onsets or offsets")
            raise ValueError(f"Invalid segment data: missing onsets or offsets")
            
        # Validate call index
        if call_to_do >= len(segment_data['onsets']) or call_to_do >= len(segment_data['offsets']):
            logger.error(f"Invalid call index {call_to_do}: out of range (max: {len(segment_data['onsets'])-1})")
            raise IndexError(f"Invalid call index {call_to_do}: out of range")
        
        # Calculate onset and offset in samples
        onset = int(segment_data['onsets'][call_to_do] * fs)
        offset = int(segment_data['offsets'][call_to_do] * fs)
        
        logger.debug(f"Call {call_to_do}: onset={onset}, offset={offset}, fs={fs}")
        
        # Validate audio data boundaries
        if onset >= len(audiodata) or offset > len(audiodata):
            logger.error(f"Invalid segment boundaries: onset={onset}, offset={offset}, audio length={len(audiodata)}")
            raise ValueError(f"Invalid segment boundaries: onset={onset}, offset={offset}, audio length={len(audiodata)}")
            
        # Extract audio segment with window padding
        start_idx = max(0, onset - (fs * hwin // 1000))
        end_idx = min(offset + (fs * hwin // 1000), len(audiodata))
        
        logger.debug(f"Extracting segment: start_idx={start_idx}, end_idx={end_idx}")
        thr_x1 = audiodata[start_idx:end_idx, :]
        
        # Mark segments that are too long or have invalid boundaries
        if (offset-onset)*1.0/fs > 1.0 or offset <= onset:
            logger.warning(f"Marking segment as error due to invalid duration or boundaries")
            fs = -fs
            
        logger.info(f"Successfully extracted audio segment: shape={thr_x1.shape}")
        return thr_x1, fs, hashof
        
    except Exception as e:
        logger.error(f"Error in get_audio_bit: {str(e)}")
        logger.debug(traceback.format_exc())
        raise
