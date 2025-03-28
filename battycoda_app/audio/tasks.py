"""
Celery tasks for BattyCoda audio and spectrogram processing.
"""
import logging
import os
import tempfile
import time
import traceback

from django.conf import settings

import numpy as np
import scipy.signal
import soundfile as sf
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


@shared_task(bind=True, name="battycoda_app.audio.tasks.generate_recording_spectrogram")
def generate_recording_spectrogram(self, recording_id):
    """
    Generate a full spectrogram for a recording.
    
    Args:
        recording_id: ID of the Recording model
        
    Returns:
        dict: Result with the spectrogram file path
    """
    import hashlib
    import os
    import tempfile

    from django.conf import settings

    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    import matplotlib.pyplot as plt
    import numpy as np
    import soundfile as sf
    from PIL import Image

    from ..models import Recording
    
    logger.info(f"Generating full spectrogram for recording {recording_id}")
    
    try:
        # Get the recording
        recording = Recording.objects.get(id=recording_id)
        
        # Get the WAV file path
        wav_path = recording.wav_file.path
        
        # Create a hash of the file path for caching
        file_hash = hashlib.md5(wav_path.encode()).hexdigest()
        
        # Create the output directory and filename
        output_dir = os.path.join(settings.MEDIA_ROOT, 'spectrograms', 'recordings')
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{file_hash}.png")
        
        # Check if file already exists
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"Spectrogram already exists at {output_path}")
            return {
                "status": "success", 
                "file_path": output_path,
                "recording_id": recording_id,
                "cached": True
            }
        
        # Load the audio file
        audio_data, sample_rate = sf.read(wav_path)
        
        # For very long recordings, downsample to improve performance
        max_duration_samples = 10 * 60 * sample_rate  # 10 minutes maximum
        if len(audio_data) > max_duration_samples:
            # Downsample by taking every nth sample
            downsample_factor = int(len(audio_data) / max_duration_samples) + 1
            audio_data = audio_data[::downsample_factor]
            effective_sample_rate = sample_rate / downsample_factor
            logger.info(f"Downsampled recording from {len(audio_data)*downsample_factor} to {len(audio_data)} samples")
        else:
            effective_sample_rate = sample_rate
        
        # If stereo, convert to mono by averaging channels
        if len(audio_data.shape) > 1 and audio_data.shape[1] > 1:
            audio_data = np.mean(audio_data, axis=1)
        
        # Generate spectrogram
        plt.figure(figsize=(20, 10))
        plt.specgram(audio_data, Fs=effective_sample_rate, cmap='viridis')
        plt.title(f"Spectrogram: {recording.name}")
        plt.xlabel('Time (s)')
        plt.ylabel('Frequency (Hz)')
        plt.colorbar(label='Intensity')
        
        # Save the figure to a temporary file first
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            temp_path = tmp_file.name
            plt.savefig(temp_path, dpi=100, bbox_inches='tight')
            plt.close()
        
        # Convert with PIL for final processing and compression
        with Image.open(temp_path) as img:
            # Apply any image processing here if needed
            img.save(output_path, format="PNG", optimize=True)
        
        # Clean up temporary file
        os.unlink(temp_path)
        
        logger.info(f"Generated spectrogram at {output_path}")
        return {
            "status": "success", 
            "file_path": output_path,
            "recording_id": recording_id,
            "cached": False
        }
        
    except Exception as e:
        logger.error(f"Error generating recording spectrogram: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "message": str(e),
            "recording_id": recording_id
        }


@shared_task(bind=True, name="battycoda_app.audio.tasks.run_call_detection")
def run_call_detection(self, detection_run_id):
    """
    Run automated call classification on segments using the configured classifier.
    
    Args:
        detection_run_id: ID of the DetectionRun model
        
    Returns:
        dict: Result of the classification process
    """
    import json
    import os
    import tempfile
    import time

    from django.conf import settings
    from django.db import transaction

    import numpy as np
    import requests

    from ..models import Call, CallProbability, Classifier, DetectionResult, DetectionRun, Segment, Segmentation
    
    logger.info(f"Starting call classification for run {detection_run_id}")
    
    try:
        # Get the detection run
        detection_run = DetectionRun.objects.get(id=detection_run_id)
        
        # Get the classifier to use
        classifier = detection_run.classifier
        
        # If no classifier is specified, try to get the default R-direct classifier
        if not classifier:
            try:
                classifier = Classifier.objects.get(name='R-direct Classifier')
                logger.info(f"Using default R-direct classifier for classification run {detection_run_id}")
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
        
        # Get all segments from the recording
        segments = Segment.objects.filter(recording=detection_run.segmentation.recording)
        total_segments = segments.count()
        
        if total_segments == 0:
            detection_run.status = "failed"
            detection_run.error_message = "No segments found in recording"
            detection_run.save()
            return {"status": "error", "message": "No segments found in recording"}
        
        # Get all possible call types for this species
        calls = Call.objects.filter(species=detection_run.segmentation.recording.species)
        
        if not calls:
            detection_run.status = "failed"
            detection_run.error_message = "No call types found for this species"
            detection_run.save()
            return {"status": "error", "message": "No call types found for this species"}
        
        # Get the recording's WAV file path
        recording = detection_run.segmentation.recording
        wav_file_path = None
        
        if recording.wav_file:
            wav_file_path = recording.wav_file.path
            logger.info(f"Using WAV file from recording: {wav_file_path}")
        
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
        
        # Process each segment by sending to the R-direct service
        for i, segment in enumerate(segments):
            try:
                # Extract audio segment from WAV file
                segment_data = extract_audio_segment(wav_file_path, segment.onset, segment.offset)
                
                # Save segment to a temporary file
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                    temp_path = temp_file.name
                    sf.write(temp_path, segment_data, samplerate=250000)  # Assuming 250kHz sampling rate
                
                # Log segment info for debugging
                logger.info(f"Created temporary file for segment {segment.id}: {temp_path}")
                logger.info(f"Segment duration: {len(segment_data)/250000:.4f}s")
                
                # Prepare files for upload
                files = {
                    'file': (f"segment_{segment.id}.wav", open(temp_path, 'rb'), 'audio/wav')
                }
                
                # Prepare parameters for the R service
                params = {
                    'species': recording.species.name,
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
                                segment=segment
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
            
            except Exception as segment_error:
                # If an error occurs, don't use fallback values - we want to know about the error
                logger.error(f"Error processing segment {segment.id}: {str(segment_error)}")
                logger.error(traceback.format_exc())
                
                # Mark the detection run as failed
                detection_run.status = "failed"
                detection_run.error_message = f"Error processing segment {segment.id}: {str(segment_error)}"
                detection_run.save()
                
                # Return error status
                return {
                    "status": "error", 
                    "message": f"Error processing segment {segment.id}: {str(segment_error)}"
                }
            
            # Update progress
            progress = ((i + 1) / total_segments) * 100
            detection_run.progress = progress
            detection_run.save()
        
        # Mark as completed
        detection_run.status = "completed"
        detection_run.progress = 100.0
        detection_run.save()
        
        return {
            "status": "success", 
            "message": f"Successfully processed {total_segments} segments using classifier: {classifier.name}",
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


@shared_task(bind=True, name="battycoda_app.audio.tasks.run_dummy_classifier")
def run_dummy_classifier(self, detection_run_id):
    """
    Dummy classifier that assigns equal probability to all call types.
    This is for testing purposes only and doesn't perform any actual classification.
    
    Args:
        detection_run_id: ID of the DetectionRun model
        
    Returns:
        dict: Result of the dummy classification process
    """
    import time
    import traceback
    from django.db import transaction
    from ..models import Call, CallProbability, DetectionResult, DetectionRun, Segment
    
    logger.info(f"Starting dummy classification for run {detection_run_id}")
    
    try:
        # Get the detection run
        detection_run = DetectionRun.objects.get(id=detection_run_id)
        
        # Update status
        detection_run.status = "in_progress"
        detection_run.save()
        
        # Get all segments from the recording
        segments = Segment.objects.filter(recording=detection_run.segmentation.recording)
        total_segments = segments.count()
        
        if total_segments == 0:
            detection_run.status = "failed"
            detection_run.error_message = "No segments found in recording"
            detection_run.save()
            return {"status": "error", "message": "No segments found in recording"}
        
        # Get all possible call types for this species
        calls = Call.objects.filter(species=detection_run.segmentation.recording.species)
        
        if not calls:
            detection_run.status = "failed"
            detection_run.error_message = "No call types found for this species"
            detection_run.save()
            return {"status": "error", "message": "No call types found for this species"}
        
        # Calculate equal probability for each call type
        equal_probability = 1.0 / calls.count()
        logger.info(f"Using equal probability of {equal_probability:.4f} for {calls.count()} call types")
        
        # Process each segment, assigning equal probability to all call types
        for i, segment in enumerate(segments):
            try:
                with transaction.atomic():
                    # Create detection result
                    result = DetectionResult.objects.create(
                        detection_run=detection_run,
                        segment=segment
                    )
                    
                    # Create equal probability for each call type
                    for call in calls:
                        CallProbability.objects.create(
                            detection_result=result,
                            call=call,
                            probability=equal_probability
                        )
                
                # Add a small delay to simulate processing time (optional)
                time.sleep(0.05)
                
                # Update progress
                progress = ((i + 1) / total_segments) * 100
                detection_run.progress = progress
                detection_run.save()
                
            except Exception as segment_error:
                logger.error(f"Error processing segment {segment.id}: {str(segment_error)}")
                logger.error(traceback.format_exc())
                
                # Mark the detection run as failed
                detection_run.status = "failed"
                detection_run.error_message = f"Error processing segment {segment.id}: {str(segment_error)}"
                detection_run.save()
                
                # Return error status
                return {
                    "status": "error", 
                    "message": f"Error processing segment {segment.id}: {str(segment_error)}"
                }
        
        # Mark as completed
        detection_run.status = "completed"
        detection_run.progress = 100.0
        detection_run.save()
        
        return {
            "status": "success", 
            "message": f"Successfully processed {total_segments} segments with dummy classifier",
            "detection_run_id": detection_run_id
        }
        
    except Exception as e:
        logger.error(f"Error in dummy classifier: {str(e)}")
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


@shared_task(bind=True, name="battycoda_app.audio.tasks.auto_segment_recording")
def auto_segment_recording_task(self, recording_id, min_duration_ms=10, smooth_window=3, threshold_factor=0.5, debug_visualization=False):
    """
    Automatically segment a recording using the steps:
    1. Take absolute value of the signal
    2. Smooth the signal using a moving average filter
    3. Apply a threshold to detect segments
    4. Reject markings shorter than the minimum duration
    
    Args:
        recording_id: ID of the Recording model to segment
        min_duration_ms: Minimum segment duration in milliseconds
        smooth_window: Window size for smoothing filter (number of samples)
        threshold_factor: Threshold factor (between 0-1) relative to signal statistics
        debug_visualization: If True, generates a visualization of the segmentation process
        
    Returns:
        dict: Result information including number of segments created and optional debug image path
    """
    from django.conf import settings
    from django.db import transaction
    import shutil

    from ..models import Recording, Segment, Segmentation
    from .utils import auto_segment_audio
    
    logger.info(f"Starting automated segmentation for recording {recording_id}")
    
    try:
        # Get the recording
        recording = Recording.objects.get(id=recording_id)
        
        # Check if recording file exists
        if not recording.wav_file or not os.path.exists(recording.wav_file.path):
            error_msg = f"WAV file not found for recording {recording_id}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
        
        # Run the automated segmentation
        try:
            # Find the segmentation record created by the view using task_id
            task_id = self.request.id
            segmentation = Segmentation.objects.get(task_id=task_id)
            
            # Determine which algorithm to use based on the segmentation's algorithm type
            algorithm = segmentation.algorithm
            algorithm_type = "threshold"  # Default
            
            if algorithm and hasattr(algorithm, 'algorithm_type'):
                algorithm_type = algorithm.algorithm_type
            
            logger.info(f"Using algorithm type: {algorithm_type} for segmentation")
            
            debug_path = None
            if debug_visualization:
                # Run with debug visualization using the appropriate algorithm
                if algorithm_type == "energy":
                    logger.info("Using energy-based segmentation algorithm")
                    from .utils import energy_based_segment_audio
                    onsets, offsets, debug_path = energy_based_segment_audio(
                        recording.wav_file.path, 
                        min_duration_ms=min_duration_ms,
                        smooth_window=smooth_window, 
                        threshold_factor=threshold_factor,
                        debug_visualization=True
                    )
                else:
                    # Default to threshold-based
                    logger.info("Using threshold-based segmentation algorithm")
                    from .utils import auto_segment_audio
                    onsets, offsets, debug_path = auto_segment_audio(
                        recording.wav_file.path, 
                        min_duration_ms=min_duration_ms,
                        smooth_window=smooth_window, 
                        threshold_factor=threshold_factor,
                        debug_visualization=True
                    )
                
                # Move the debug image to a more permanent location in media directory
                if debug_path and os.path.exists(debug_path):
                    # Create directory for debug visualizations if it doesn't exist
                    debug_dir = os.path.join(settings.MEDIA_ROOT, 'segmentation_debug')
                    os.makedirs(debug_dir, exist_ok=True)
                    
                    # Create a unique filename using recording ID and timestamp
                    from django.utils import timezone
                    debug_filename = f"segmentation_debug_{recording_id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.png"
                    permanent_debug_path = os.path.join(debug_dir, debug_filename)
                    
                    # Copy the file to the permanent location
                    shutil.copy(debug_path, permanent_debug_path)
                    
                    # Remove the temporary file
                    try:
                        os.unlink(debug_path)
                    except:
                        pass  # Ignore errors when cleaning up temporary file
                    
                    # Update debug_path to the permanent location
                    debug_path = permanent_debug_path
                    
                    # Get the URL-friendly path (relative to MEDIA_ROOT)
                    from django.conf import settings
                    debug_url = permanent_debug_path.replace(settings.MEDIA_ROOT, '').lstrip('/')
                    
                    logger.info(f"Saved segmentation debug visualization to {permanent_debug_path}")
            else:
                # Run without debug visualization using the appropriate algorithm
                if algorithm_type == "energy":
                    logger.info("Using energy-based segmentation algorithm")
                    from .utils import energy_based_segment_audio
                    onsets, offsets = energy_based_segment_audio(
                        recording.wav_file.path, 
                        min_duration_ms=min_duration_ms,
                        smooth_window=smooth_window, 
                        threshold_factor=threshold_factor
                    )
                else:
                    # Default to threshold-based
                    logger.info("Using threshold-based segmentation algorithm")
                    from .utils import auto_segment_audio 
                    onsets, offsets = auto_segment_audio(
                        recording.wav_file.path, 
                        min_duration_ms=min_duration_ms,
                        smooth_window=smooth_window, 
                        threshold_factor=threshold_factor
                    )
        except Exception as e:
            error_msg = f"Error during auto-segmentation: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return {"status": "error", "message": error_msg}
        
        # Create database segments from the detected onsets/offsets
        segments_created = 0
        
        with transaction.atomic():
            # Find the segmentation record created by the view using task_id
            task_id = self.request.id
            logger.info(f"Looking for segmentation with task_id: {task_id}")
            
            # Get the existing segmentation created by the view
            segmentation = Segmentation.objects.get(task_id=task_id)
            logger.info(f"Found existing segmentation: {segmentation.id} - {segmentation.name}")
            
            # Update the segmentation status to completed
            segmentation.status = 'completed'
            segmentation.progress = 100
            segmentation.save()
            
            # Create segments for each onset/offset pair
            for i in range(len(onsets)):
                try:
                    # Generate segment name
                    segment_name = f"Auto Segment {i+1}"
                    
                    # Create segment and associate with the new segmentation
                    segment = Segment(
                        recording=recording,
                        segmentation=segmentation,
                        name=segment_name,
                        onset=onsets[i],
                        offset=offsets[i],
                        created_by=recording.created_by,  # Use recording's creator
                        notes="Created by automated segmentation"
                    )
                    segment.save(manual_edit=False)  # Don't mark as manually edited for automated segmentation
                    segments_created += 1
                except Exception as e:
                    logger.error(f"Error creating segment {i}: {str(e)}")
                    # Continue with other segments
        
        # Return success result
        logger.info(f"Successfully created {segments_created} segments from automated detection")
        result = {
            "status": "success",
            "recording_id": recording_id,
            "segments_created": segments_created,
            "total_segments_found": len(onsets),
            "parameters": {
                "min_duration_ms": min_duration_ms,
                "smooth_window": smooth_window,
                "threshold_factor": threshold_factor
            }
        }
        
        # Add debug visualization information if available
        if debug_visualization and debug_path:
            # Add the relative URL path for web access
            result["debug_visualization"] = {
                "file_path": debug_path,
                "url": f"/media/segmentation_debug/{os.path.basename(debug_path)}"
            }
        
        return result
        
    except Exception as e:
        logger.error(f"Error in auto_segment_recording_task: {str(e)}")
        logger.error(traceback.format_exc())
        return {"status": "error", "message": str(e)}


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

        # Check if this spectrogram is generated on-the-fly - if so, use inverted colors
        if args.get("generated_on_fly") == "1":
            logger.info("Generating on-the-fly spectrogram with inverted colors")
            # Inverted colormap (yellow-green instead of purple-blue)
            # R channel - more for brighter areas
            rgb_data[:, :, 0] = np.clip(img_data * 0.9, 0, 255).astype(np.uint8)
            # G channel - more overall
            rgb_data[:, :, 1] = np.clip(img_data * 0.8, 0, 255).astype(np.uint8)
            # B channel - less in all areas
            rgb_data[:, :, 2] = np.clip(img_data * 0.3, 0, 255).astype(np.uint8)
        else:
            # Standard colormap: convert grayscale to indigo-purple
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
