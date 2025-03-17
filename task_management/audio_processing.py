"""
Audio processing functions for task management.
"""
import os
import re
import logging
import subprocess
import numpy as np

# Set up logging
logger = logging.getLogger('battykoda.task_management.audio_processing')

# R is installed now, so set to True
R = True

def run_r_classification(wav_file_path, onset, offset, species):
    """
    Run the R script to classify a bat call.
    
    Args:
        wav_file_path (str): Path to the WAV file
        onset (float): Start time of the call
        offset (float): End time of the call
        species (str): Species of bat
        
    Returns:
        tuple: (call_type, confidence) where call_type is a string and confidence is a float
    """
    # Default values in case of errors
    default_call_type = 'Echo'
    default_confidence = 50.0
    
    try:
        # Use the classify_call.R script
        r_script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "classify_call.R")
        
        # Remove trailing slash if it exists
        if wav_file_path.endswith('/'):
            wav_file_path = wav_file_path.rstrip('/')
            logger.info(f"Removed trailing slash: {wav_file_path}")
        
        # Log the command details
        cmd = [
            "Rscript",
            "--vanilla",
            r_script_path,
            wav_file_path,
            str(onset),
            str(offset),
            species
        ]
        logger.info(f"Running R script: {' '.join(cmd)}")
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
            return default_call_type, default_confidence
        
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
            
            call_type = type_match.group(1) if type_match else default_call_type
            confidence = float(conf_match.group(1)) if conf_match else default_confidence
            
            if type_match:
                logger.info(f"Extracted type: {call_type}")
            else:
                logger.warning("Could not extract type, using default 'Echo'")
                
            if conf_match:
                logger.info(f"Extracted confidence: {confidence}")
            else:
                logger.warning("Could not extract confidence, using default 50.0")
        else:
            logger.warning("Could not parse R output correctly")
            call_type = default_call_type
            confidence = default_confidence
            
        # Make sure confidence is between 0 and 100
        confidence = max(0, min(100, confidence))
        return call_type, confidence
        
    except Exception as e:
        logger.error(f"Error running R script: {str(e)}")
        return default_call_type, default_confidence