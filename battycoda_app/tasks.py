import logging

from celery import shared_task

logger = logging.getLogger("battycoda.tasks")


@shared_task
def process_audio_file(file_path):
    """
    Process an uploaded audio file

    This is a placeholder task that can be expanded for audio processing
    """
    logger.info(f"Processing audio file: {file_path}")
    # TODO: Implement actual audio processing
    return True


@shared_task
def calculate_audio_duration(recording_id):
    """
    Calculate and update the duration and sample rate for a recording
    
    This task is triggered after a recording is saved, to ensure
    the file is fully committed to disk before processing.
    """
    from .models import Recording
    import os
    import soundfile as sf
    
    logger.info(f"Calculating audio info for recording ID: {recording_id}")
    
    try:
        # Get the recording from the database
        recording = Recording.objects.get(id=recording_id)
        
        # Skip if both duration and sample rate are already set
        if recording.duration and recording.sample_rate:
            logger.info(f"Recording {recording_id} already has duration: {recording.duration}s, sample rate: {recording.sample_rate}Hz")
            return True
            
        # Check if file exists
        if not os.path.exists(recording.wav_file.path):
            logger.error(f"File does not exist: {recording.wav_file.path}")
            return False
            
        # Extract audio information from file
        info = sf.info(recording.wav_file.path)
        duration = info.duration
        sample_rate = info.samplerate
        
        # Update the recording
        update_fields = []
        
        # Only update duration if it's not already set
        if not recording.duration:
            recording.duration = duration
            update_fields.append('duration')
            
        # Only update sample_rate if it's not already set
        if not recording.sample_rate:
            recording.sample_rate = sample_rate
            update_fields.append('sample_rate')
        
        # Use update_fields to avoid triggering save signal again (if any fields were updated)
        if update_fields:
            recording.save(update_fields=update_fields)
            logger.info(f"Successfully updated recording {recording_id}: duration={duration}s, sample_rate={sample_rate}Hz")
        
        return True
        
    except Recording.DoesNotExist:
        logger.error(f"Recording with ID {recording_id} does not exist")
        return False
    except Exception as e:
        logger.error(f"Error calculating audio info for recording {recording_id}: {str(e)}")
        return False


@shared_task
def generate_spectrogram(file_path, output_path=None):
    """
    Generate a spectrogram from an audio file

    This is a placeholder task that can be expanded for spectrogram generation
    """
    logger.info(f"Generating spectrogram for: {file_path}")
    # TODO: Implement actual spectrogram generation
    return True
