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
    Classify a bat call using either the R server API or fallback to direct R script.
    
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
    
    # First, try using the R server API if available
    try:
        import requests
        import json
        
        # The URL of the R server - first try the direct KNN version, then fallback to the regular one
        r_server_urls = ["http://localhost:8000", "http://localhost:8001"]
        r_server_url = r_server_urls[0]  # Default to the first server
        
        # Try to ping the server to see if it's available
        try:
            # Try each server URL in order
            server_connected = False
            
            for server_url in r_server_urls:
                try:
                    logger.info(f"Trying R server at {server_url}")
                    response = requests.get(f"{server_url}/ping", timeout=2)
                    
                    if response.status_code == 200:
                        server_status = response.json()
                        if server_status.get('model_loaded', False):
                            logger.info(f"R server is running with model loaded: {server_url}")
                            r_server_url = server_url
                            server_connected = True
                            break
                        else:
                            logger.warning(f"R server is running but model is not loaded: {server_url}")
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Could not connect to R server at {server_url}: {str(e)}")
            
            if not server_connected:
                logger.error("Could not connect to any R server, falling back to direct R script")
                raise Exception("No R server available")
                    
            # Send classification request to the server
            data = {
                'wav_path': wav_file_path,
                'onset': onset,
                'offset': offset,
                'species': species
            }
            
            logger.info(f"Sending classification request to R server: {r_server_url}")
            classify_response = requests.post(f"{r_server_url}/classify", data=data, timeout=10)
            
            if classify_response.status_code == 200:
                # Parse the response
                result = classify_response.json()
                logger.info(f"R server classification result: {json.dumps(result)}")
                
                if result.get('status')[0] == 'success':
                    call_type = result.get('call_type', default_call_type)[0]
                    confidence = result.get('confidence', default_confidence)[0]
                    logger.info(f"R server classification: {call_type}, confidence: {confidence}")
                    return call_type, confidence
                else:
                    # Server error, log the error message
                    error_message = result.get('message', 'Unknown server error')
                    logger.error(f"R server classification error: {error_message}")
                    # Fall back to direct R script
            else:
                logger.error(f"R server classification failed with status code: {classify_response.status_code}")
                # Fall back to direct R script
        except requests.exceptions.RequestException as e:
            # Connection error, server probably not running
            logger.warning(f"Could not connect to R server: {str(e)}")
            # Fall back to direct R script
    except ImportError:
        # Requests library not available
        logger.warning("Python requests library not available, falling back to direct R script")
        # Fall back to direct R script
    
    # If we get here, the R server approach failed, so fall back to using the R script directly
    logger.info("Falling back to direct R script for classification")
    
    try:
        # Use the classify_call.R script - get absolute path to ensure we can find it
        r_script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "classify_call.R")
        
        # Verify the model file exists
        model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static/mymodel.RData")
        if os.path.exists(model_path):
            logger.info(f"Model file found at: {model_path}")
        else:
            logger.error(f"Model file not found at: {model_path}")
        
        # Remove trailing slash if it exists
        if wav_file_path.endswith('/'):
            wav_file_path = wav_file_path.rstrip('/')
            logger.info(f"Removed trailing slash: {wav_file_path}")
            
        # Verify the WAV file exists
        if os.path.exists(wav_file_path):
            logger.info(f"WAV file found at: {wav_file_path}")
        else:
            logger.error(f"WAV file not found at: {wav_file_path}")
            
        # Check if R is available
        try:
            r_version = subprocess.run(
                ["Rscript", "--version"],
                capture_output=True,
                text=True,
                check=False
            )
            logger.info(f"R version: {r_version.stderr.strip() if r_version.stderr else 'unknown'}")
        except Exception as e:
            logger.error(f"Error checking R version: {str(e)}")
        
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
            check=False,  # Don't raise exception on non-zero exit
            env=dict(os.environ, R_LIBS_USER=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".r_libs"))
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
        
        # Check for the specific default confidence value (60.0 or 85.0) to diagnose model loading issues
        if "confidence: 60.0" in returnvalue.stdout or "confidence: 85.0" in returnvalue.stdout:
            logger.warning("Detected default confidence value - model loading likely failed")
            
            # Check for model loading errors
            for line in stdout_lines:
                if "Unable to load model" in line or "Error loading model" in line:
                    logger.error(f"Model loading error detected: {line}")
                    
                if "Error making prediction" in line:
                    logger.error(f"Prediction error detected: {line}")
        
        # Log all lines for debugging
        for i, line in enumerate(stdout_lines):
            logger.debug(f"Line {i}: {line}")
        
        # Look for lines containing call type and confidence values
        # The script outputs in a consistent format: "type: 'X'" and "confidence: Y.Z"
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
                # Check if we're getting the default 60.0 value that indicates model loading issues
                if confidence == 60.0:
                    logger.warning("Default confidence value detected - model may not be loading properly")
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