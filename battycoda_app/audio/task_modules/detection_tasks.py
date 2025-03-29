"""
Call detection tasks for BattyCoda.
"""
import json
import os
import time
import traceback

import numpy as np
import requests
import soundfile as sf
from celery import shared_task

from .base import extract_audio_segment, logger


@shared_task(bind=True, name="battycoda_app.audio.task_modules.detection_tasks.run_call_detection")
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

    from ...models import Call, CallProbability, Classifier, DetectionResult, DetectionRun, Segment, Segmentation

    logger.info(f"Starting call classification for run {detection_run_id}")

    try:
        # Get the detection run
        detection_run = DetectionRun.objects.get(id=detection_run_id)

        # Get the classifier to use
        classifier = detection_run.classifier

        # If no classifier is specified, try to get the default R-direct classifier
        if not classifier:
            try:
                classifier = Classifier.objects.get(name="R-direct Classifier")
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
                segment_data, sample_rate = extract_audio_segment(wav_file_path, segment.onset, segment.offset)

                # Save segment to a temporary file
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                    temp_path = temp_file.name
                    sf.write(temp_path, segment_data, samplerate=sample_rate)

                # Log segment info for debugging
                logger.info(f"Created temporary file for segment {segment.id}: {temp_path}")
                logger.info(f"Segment duration: {len(segment_data)/sample_rate:.4f}s, sample rate: {sample_rate}Hz")

                # Prepare files for upload
                files = {"file": (f"segment_{segment.id}.wav", open(temp_path, "rb"), "audio/wav")}

                # Prepare parameters for the R service
                params = {
                    "species": recording.species.name,
                    "call_types": ",".join([call.short_name for call in calls]),
                }

                # Log request details
                logger.info(f"Sending request to {endpoint} with params: {params}")

                # Make request to classifier service
                response = requests.post(endpoint, files=files, params=params, timeout=30)  # 30 second timeout

                # Close file handle and clean up temporary file
                files["file"][1].close()
                os.unlink(temp_path)

                # Log response information
                logger.info(f"R-direct response status: {response.status_code}")
                logger.info(f"R-direct response headers: {response.headers}")
                if response.headers.get("Content-Type", "").startswith("application/json"):
                    logger.info(f"R-direct response content (first 500 chars): {response.text[:500]}")

                # Process response
                if response.status_code == 200:
                    try:
                        prediction_data = response.json()
                        logger.info(f"Parsed prediction data: {prediction_data}")

                        with transaction.atomic():
                            # Create detection result
                            result = DetectionResult.objects.create(detection_run=detection_run, segment=segment)

                            # Process results based on classifier response format
                            if classifier.response_format == "highest_only":
                                # For highest-only algorithm type
                                if "predicted_call" in prediction_data and "confidence" in prediction_data:
                                    predicted_call_name = prediction_data["predicted_call"]
                                    confidence = float(prediction_data["confidence"])

                                    # Ensure confidence is within valid range
                                    confidence = max(0.0, min(1.0, confidence))

                                    # Find the call by name
                                    try:
                                        predicted_call = next(
                                            call for call in calls if call.short_name == predicted_call_name
                                        )

                                        # Create a probability record for the predicted call
                                        CallProbability.objects.create(
                                            detection_result=result, call=predicted_call, probability=confidence
                                        )

                                        # Create zero probability records for all other calls
                                        for call in calls:
                                            if call.short_name != predicted_call_name:
                                                CallProbability.objects.create(
                                                    detection_result=result, call=call, probability=0.0
                                                )
                                    except StopIteration:
                                        # Call not found
                                        error_msg = (
                                            f"Predicted call '{predicted_call_name}' not found in available calls"
                                        )
                                        logger.error(error_msg)
                                        raise ValueError(error_msg)
                                else:
                                    # Missing required fields for highest-only algorithm
                                    error_msg = (
                                        f"Missing required fields in highest-only algorithm response: {prediction_data}"
                                    )
                                    logger.error(error_msg)
                                    raise ValueError(error_msg)
                            else:
                                # For full probability distribution algorithm type
                                if "probabilities" in prediction_data:
                                    probabilities = prediction_data["probabilities"]

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
                                            detection_result=result, call=call, probability=prob_value
                                        )
                                else:
                                    # Missing probabilities in response
                                    error_msg = (
                                        f"Missing probabilities in full distribution response: {prediction_data}"
                                    )
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
                return {"status": "error", "message": f"Error processing segment {segment.id}: {str(segment_error)}"}

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
            "detection_run_id": detection_run_id,
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


@shared_task(bind=True, name="battycoda_app.audio.task_modules.detection_tasks.run_dummy_classifier")
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

    from ...models import Call, CallProbability, DetectionResult, DetectionRun, Segment

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
                    result = DetectionResult.objects.create(detection_run=detection_run, segment=segment)

                    # Create equal probability for each call type
                    for call in calls:
                        CallProbability.objects.create(
                            detection_result=result, call=call, probability=equal_probability
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
                return {"status": "error", "message": f"Error processing segment {segment.id}: {str(segment_error)}"}

        # Mark as completed
        detection_run.status = "completed"
        detection_run.progress = 100.0
        detection_run.save()

        return {
            "status": "success",
            "message": f"Successfully processed {total_segments} segments with dummy classifier",
            "detection_run_id": detection_run_id,
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
