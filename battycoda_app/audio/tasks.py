"""
Celery tasks for BattyCoda audio and spectrogram processing.
"""
import logging
import os
import shutil
import tempfile
import time
import traceback

from django.conf import settings

import numpy as np
import scipy.signal
from celery import current_app, group, shared_task
from PIL import Image

from ..utils import convert_path_to_os_specific
from .utils import appropriate_file, get_audio_bit, normal_hwin, overview_hwin

# Configure logging
logger = logging.getLogger("battycoda.tasks")


# Create a timer function for performance tracking - with minimal output
def log_performance(start_time, message):
    """Log performance with elapsed time - only for total task time"""
    # Only log total task completions to reduce log volume
    if "TOTAL" in message:
        elapsed = time.time() - start_time
        logger.info(f"PERF: {message} - {elapsed:.3f}s")


# No need for matplotlib configuration anymore


@shared_task(bind=True, name="battycoda_app.audio.tasks.generate_spectrogram_task", max_retries=3, retry_backoff=True)
def generate_spectrogram_task(self, path, args, output_path=None):
    """
    Task to generate a spectrogram image.

    Args:
        path: Path to the audio file
        args: Dict of parameters (call, channel, etc.)
        output_path: Optional explicit output path

    Returns:
        dict: Result information
    """
    start_time = time.time()

    # Create minimal task identifier for logging
    call = args.get("call", "?")
    channel = args.get("channel", "?")
    task_id = f"Call {call} Ch {channel}"

    try:
        # Skip state updates to reduce logs

        # Get file paths
        if output_path is None:
            output_path = appropriate_file(path, args)

        # Convert URL path to OS path (if not already converted)
        if path.startswith("home/"):
            os_path = convert_path_to_os_specific(path)
        else:
            os_path = path

        # Generate the spectrogram
        success, output_file, error = generate_spectrogram(os_path, args, output_path)

        # Only log results for failures
        if not success:
            logger.error(f"{task_id} FAILED: {error}")

        if success:
            return {"status": "success", "file_path": output_file, "original_path": path, "args": args}
        else:
            return {
                "status": "error",
                "error": error if error else "Failed to generate spectrogram",
                "file_path": output_file,
            }

    except Exception as e:
        # Only log full errors for catastrophic failures
        logger.error(f"{task_id} CATASTROPHIC ERROR: {str(e)}")

        # Retry the task if appropriate
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=2**self.request.retries)

        return {"status": "error", "error": str(e), "path": path, "args": args}


@shared_task(bind=True, name="audio.prefetch_spectrograms")
def prefetch_spectrograms(self, path, base_args, call_range):
    """
    Prefetch multiple spectrograms for a range of calls.
    DISABLED - This function now does nothing to reduce server load

    Args:
        path: Path to the audio file
        base_args: Base arguments dict
        call_range: Tuple of (start_call, end_call)

    Returns:
        dict: Status indicating the function is disabled
    """
    logger.info("Prefetching is disabled for performance reasons")

    # Return a summary indicating prefetch is disabled
    return {"status": "disabled", "message": "Prefetching is disabled for performance reasons"}


@shared_task(bind=True, name="battycoda_app.audio.tasks.run_call_detection")
def run_call_detection(self, detection_run_id):
    """
    Run automated call detection on a batch using the configured classifier.
    
    Args:
        detection_run_id: ID of the DetectionRun model
        
    Returns:
        dict: Result of the detection process
    """
    from django.db import transaction
    from django.conf import settings
    from ..models import DetectionRun, DetectionResult, CallProbability, Task, Call, Classifier
    import os
    import requests
    import json
    import time
    import tempfile
    import soundfile as sf
    import numpy as np
    
    logger.info(f"Starting call detection for run {detection_run_id}")
    
    try:
        # Get the detection run
        detection_run = DetectionRun.objects.get(id=detection_run_id)
        
        # Get the classifier to use
        classifier = detection_run.classifier
        
        # If no classifier is specified, try to get the default R-direct classifier
        if not classifier:
            try:
                classifier = Classifier.objects.get(name='R-direct Classifier')
                logger.info(f"Using default R-direct classifier for detection run {detection_run_id}")
            except Classifier.DoesNotExist:
                error_msg = "No classifier specified and default R-direct classifier not found"
                logger.error(error_msg)
                detection_run.status = "failed"
                detection_run.error_message = error_msg
                detection_run.save()
                return {"status": "error", "message": error_msg}
                
        # Configure the service URL and endpoint
        service_url = classifier.service_url
        endpoint = f"{service_url}{classifier.endpoint}"
        
        logger.info(f"Using classifier: {classifier.name} ({classifier.id})")
        logger.info(f"Service URL: {service_url}, Endpoint: {endpoint}")
        
        # Update status
        detection_run.status = "in_progress"
        detection_run.save()
        
        # Get all tasks in the batch
        tasks = Task.objects.filter(batch=detection_run.batch)
        total_tasks = tasks.count()
        
        if total_tasks == 0:
            detection_run.status = "failed"
            detection_run.error_message = "No tasks found in batch"
            detection_run.save()
            return {"status": "error", "message": "No tasks found in batch"}
        
        # Get all possible call types for this species
        calls = Call.objects.filter(species=detection_run.batch.species)
        
        if not calls:
            detection_run.status = "failed"
            detection_run.error_message = "No call types found for this species"
            detection_run.save()
            return {"status": "error", "message": "No call types found for this species"}
        
        # Get the batch's WAV file path
        batch = detection_run.batch
        wav_file_path = None
        
        if batch.wav_file:
            wav_file_path = batch.wav_file.path
            logger.info(f"Using WAV file from batch: {wav_file_path}")
        
        if not wav_file_path or not os.path.exists(wav_file_path):
            detection_run.status = "failed"
            detection_run.error_message = f"WAV file not found: {wav_file_path}"
            detection_run.save()
            return {"status": "error", "message": f"WAV file not found: {wav_file_path}"}
        
        # Test the service connection before processing
        try:
            ping_response = requests.get(f"{service_url}/ping", timeout=5)
            if ping_response.status_code != 200:
                error_msg = f"Classifier service unavailable. Status: {ping_response.status_code}"
                logger.error(error_msg)
                detection_run.status = "failed"
                detection_run.error_message = error_msg
                detection_run.save()
                return {"status": "error", "message": error_msg}
                
            logger.info(f"Classifier service is available: {ping_response.text}")
        except requests.RequestException as e:
            error_msg = f"Cannot connect to classifier service: {str(e)}"
            logger.error(error_msg)
            detection_run.status = "failed"
            detection_run.error_message = error_msg
            detection_run.save()
            return {"status": "error", "message": error_msg}
        
        # Process each task by sending segments to R-direct service
        for i, task in enumerate(tasks):
            try:
                # Extract audio segment from WAV file
                segment_data = extract_audio_segment(wav_file_path, task.onset, task.offset)
                
                # Save segment to a temporary file
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                    temp_path = temp_file.name
                    sf.write(temp_path, segment_data, samplerate=250000)  # Assuming 250kHz sampling rate
                
                # Log segment info for debugging
                logger.info(f"Created temporary file for task {task.id}: {temp_path}")
                logger.info(f"Segment duration: {len(segment_data)/250000:.4f}s")
                
                # Prepare files for upload
                files = {
                    'file': (f"segment_{task.id}.wav", open(temp_path, 'rb'), 'audio/wav')
                }
                
                # Prepare parameters for the R service
                params = {
                    'species': batch.species.name,
                    'call_types': ','.join([call.short_name for call in calls])
                }
                
                # Log request details
                logger.info(f"Sending request to {endpoint} with params: {params}")
                
                # Make request to classifier service
                response = requests.post(
                    endpoint,
                    files=files,
                    params=params,
                    timeout=30  # 30 second timeout
                )
                
                # Close file handle and clean up temporary file
                files['file'][1].close()
                os.unlink(temp_path)
                
                # Log response information
                logger.info(f"R-direct response status: {response.status_code}")
                logger.info(f"R-direct response headers: {response.headers}")
                if response.headers.get('Content-Type', '').startswith('application/json'):
                    logger.info(f"R-direct response content (first 500 chars): {response.text[:500]}")
                
                # Process response
                if response.status_code == 200:
                    try:
                        prediction_data = response.json()
                        logger.info(f"Parsed prediction data: {prediction_data}")
                        
                        with transaction.atomic():
                            # Create detection result
                            result = DetectionResult.objects.create(
                                detection_run=detection_run,
                                task=task
                            )
                            
                            # Process results based on classifier response format
                            if classifier.response_format == "highest_only":
                                # For highest-only algorithm type
                                if 'predicted_call' in prediction_data and 'confidence' in prediction_data:
                                    predicted_call_name = prediction_data['predicted_call']
                                    confidence = float(prediction_data['confidence'])
                                    
                                    # Ensure confidence is within valid range
                                    confidence = max(0.0, min(1.0, confidence))
                                    
                                    # Find the call by name
                                    try:
                                        predicted_call = next(call for call in calls if call.short_name == predicted_call_name)
                                        
                                        # Create a probability record for the predicted call
                                        CallProbability.objects.create(
                                            detection_result=result,
                                            call=predicted_call,
                                            probability=confidence
                                        )
                                        
                                        # Create zero probability records for all other calls
                                        for call in calls:
                                            if call.short_name != predicted_call_name:
                                                CallProbability.objects.create(
                                                    detection_result=result,
                                                    call=call,
                                                    probability=0.0
                                                )
                                    except StopIteration:
                                        # Call not found
                                        error_msg = f"Predicted call '{predicted_call_name}' not found in available calls"
                                        logger.error(error_msg)
                                        raise ValueError(error_msg)
                                else:
                                    # Missing required fields for highest-only algorithm
                                    error_msg = f"Missing required fields in highest-only algorithm response: {prediction_data}"
                                    logger.error(error_msg)
                                    raise ValueError(error_msg)
                            else:
                                # For full probability distribution algorithm type
                                if 'probabilities' in prediction_data:
                                    probabilities = prediction_data['probabilities']
                                    
                                    for call in calls:
                                        # The R service may return results in different formats
                                        # Handle both dictionary and list formats
                                        if isinstance(probabilities, dict):
                                            # Dictionary format with call names as keys
                                            prob_value = probabilities.get(call.short_name, 0)
                                        elif isinstance(probabilities, list) and len(calls) == len(probabilities):
                                            # List format with probabilities in same order as calls
                                            call_index = list(calls).index(call)
                                            prob_value = probabilities[call_index]
                                        else:
                                            # Cannot determine probability, log error and set to 0
                                            logger.error(f"Unexpected probability format: {type(probabilities)}")
                                            prob_value = 0
                                        
                                        # Ensure probability is within valid range
                                        prob_value = max(0.0, min(1.0, float(prob_value)))
                                        
                                        # Create probability record
                                        CallProbability.objects.create(
                                            detection_result=result,
                                            call=call,
                                            probability=prob_value
                                        )
                                else:
                                    # Missing probabilities in response
                                    error_msg = f"Missing probabilities in full distribution response: {prediction_data}"
                                    logger.error(error_msg)
                                    raise ValueError(error_msg)
                    except (ValueError, json.JSONDecodeError) as parse_error:
                        # Failed to parse response
                        error_msg = f"Failed to parse classifier response: {str(parse_error)}"
                        logger.error(error_msg)
                        logger.error(f"Response content: {response.text[:1000]}")
                        raise ValueError(error_msg)
                else:
                    # Service returned an error status
                    error_msg = f"Classifier service error: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
            
            except Exception as task_error:
                # If an error occurs, don't use fallback values - we want to know about the error
                logger.error(f"Error processing task {task.id}: {str(task_error)}")
                logger.error(traceback.format_exc())
                
                # Mark the detection run as failed
                detection_run.status = "failed"
                detection_run.error_message = f"Error processing task {task.id}: {str(task_error)}"
                detection_run.save()
                
                # Return error status
                return {
                    "status": "error", 
                    "message": f"Error processing task {task.id}: {str(task_error)}"
                }
            
            # Update progress
            progress = ((i + 1) / total_tasks) * 100
            detection_run.progress = progress
            detection_run.save()
        
        # Mark as completed
        detection_run.status = "completed"
        detection_run.progress = 100.0
        detection_run.save()
        
        return {
            "status": "success", 
            "message": f"Successfully processed {total_tasks} tasks using classifier: {classifier.name}",
            "detection_run_id": detection_run_id
        }
        
    except Exception as e:
        logger.error(f"Error in call detection: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Update run status
        try:
            detection_run = DetectionRun.objects.get(id=detection_run_id)
            detection_run.status = "failed"
            detection_run.error_message = str(e)
            detection_run.save()
        except Exception as update_error:
            logger.error(f"Failed to update detection run status: {str(update_error)}")
        
        return {"status": "error", "message": str(e)}


def extract_audio_segment(wav_path, onset, offset, padding=0.01):
    """
    Extract a segment of audio from a WAV file.
    
    Args:
        wav_path: Path to the WAV file
        onset: Start time in seconds
        offset: End time in seconds
        padding: Optional padding in seconds to add before/after segment
        
    Returns:
        numpy.ndarray: Audio segment data
    """
    try:
        # Load the audio file
        audio_data, sample_rate = sf.read(wav_path)
        
        # Log file information
        logger.info(f"Loaded audio file {wav_path}: {len(audio_data)} samples, {sample_rate}Hz")
        
        # Calculate sample indices with padding
        start_sample = max(0, int((onset - padding) * sample_rate))
        end_sample = min(len(audio_data), int((offset + padding) * sample_rate))
        
        # Log segment bounds
        logger.info(f"Extracting segment from {onset-padding:.4f}s to {offset+padding:.4f}s")
        logger.info(f"Sample indices: {start_sample} to {end_sample} (length: {end_sample-start_sample})")
        
        # Extract the segment
        segment = audio_data[start_sample:end_sample]
        
        return segment
    except Exception as e:
        logger.error(f"Error extracting audio segment: {str(e)}")
        logger.error(f"File: {wav_path}, Onset: {onset}, Offset: {offset}")
        logger.error(traceback.format_exc())
        raise


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
    # Start performance timer
    start_time = time.time()

    if output_path is None:
        output_path = appropriate_file(path, args)

    # Extract basic parameters for minimal task ID
    call = args.get("call", "0")
    channel = args.get("channel", "0")
    task_id = f"Call {call} Ch {channel}"

    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Parse parameters
        call_to_do = int(args.get("call", 0))
        overview = args.get("overview") == "1" or args.get("overview") == "True"
        channel = int(args.get("channel", 0))
        contrast = float(args.get("contrast", 4))

        # Select window size
        hwin = overview_hwin() if overview else normal_hwin()

        # Get audio data with direct segment loading if possible
        extra_params = None
        if "onset" in args and "offset" in args:
            extra_params = {"onset": args["onset"], "offset": args["offset"]}

        thr_x1, fs, hashof = get_audio_bit(path, call_to_do, hwin, extra_params)

        # Validate audio data
        if thr_x1 is None or thr_x1.size == 0:
            return False, output_path, "Audio data is empty"

        # Check channel is valid
        if channel >= thr_x1.shape[1]:
            return False, output_path, f"Channel index {channel} is out of bounds"

        # Extract channel
        thr_x1 = thr_x1[:, channel]

        # OPTIMIZATION: Skip hash validation to reduce overhead
        # This is safe because we're using file paths that are already validated

        # Use high-quality spectrogram parameters for better visual detail
        # - Higher nperseg for better frequency resolution
        # - Higher overlap for smoother time transitions
        # - Larger nfft for better frequency bins
        if overview:
            # For overview, use very high detail since we're showing more
            nperseg = 2**9  # 512
            noverlap = int(nperseg * 0.99)  # 99% overlap for highest quality
            nfft = 2**10  # 1024 for excellent frequency resolution
        else:
            # For call detail view, use high quality parameters
            nperseg = 2**8  # 256
            noverlap = 254
            nfft = 2**8

        # Generate spectrogram with optimized parameters
        f, t, sxx = scipy.signal.spectrogram(thr_x1, fs, nperseg=nperseg, noverlap=noverlap, nfft=nfft)

        # Process data for image creation - measure time
        process_start = time.time()

        # Apply contrast enhancement
        temocontrast = 10**contrast
        processed_data = np.arctan(temocontrast * sxx)

        # Normalize the data to 0-255 range for image
        processed_data = (processed_data - processed_data.min()) / (processed_data.max() - processed_data.min()) * 255

        # Flip the spectrogram vertically (low frequencies at bottom)
        processed_data = np.flipud(processed_data)

        # Convert to 8-bit unsigned integer
        img_data = processed_data.astype(np.uint8)

        # For a more colorful image, you can create an RGB version:
        # Here we're using a purple-blue colormap similar to the original
        height, width = img_data.shape
        rgb_data = np.zeros((height, width, 3), dtype=np.uint8)

        # Simple colormap: convert grayscale to indigo-purple
        # R channel - more for brighter areas
        rgb_data[:, :, 0] = np.clip(img_data * 0.7, 0, 255).astype(np.uint8)
        # G channel - less overall
        rgb_data[:, :, 1] = np.clip(img_data * 0.2, 0, 255).astype(np.uint8)
        # B channel - more in all areas for blue/indigo base
        rgb_data[:, :, 2] = np.clip(img_data * 0.9, 0, 255).astype(np.uint8)

        log_performance(process_start, f"{task_id}: Process spectrogram data")

        # Create and save image - measure time
        img_start = time.time()

        # Create PIL Image and save
        img = Image.fromarray(rgb_data)

        # Resize to standard dimensions (800x600)
        img = img.resize((800, 600), Image.Resampling.LANCZOS)

        # Save with minimal compression for speed
        img.save(output_path, format="PNG", compress_level=1)

        log_performance(img_start, f"{task_id}: Create and save image")

        # Verify the file was created and log performance
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            log_performance(start_time, f"{task_id}: TOTAL SPECTROGRAM GENERATION")
            return True, output_path, None
        else:
            logger.error(f"ERROR: Output file not created properly: {output_path}")
            return False, output_path, "Failed to create output file"

    except Exception as e:
        logger.error(f"Error generating spectrogram: {str(e)}")
        # Simply return the error, no attempt to create error image
        return False, output_path, str(e)
