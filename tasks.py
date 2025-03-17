"""
Celery tasks for BattyCoda.
This module defines all the asynchronous tasks that can be executed by Celery workers.
"""
import os
import time
import logging
import traceback
from celery import group
from celery.signals import task_prerun, task_postrun, task_failure
from celery_app import celery
import utils
from spectrogram_generator import generate_spectrogram, create_error_image
from AppropriateFile import appropriate_file

# Configure logging
logger = logging.getLogger('battykoda.tasks')

# ----- Task monitoring and metrics -----

@task_prerun.connect
def task_started(sender=None, task_id=None, task=None, args=None, kwargs=None, **_):
    """Log when a task starts."""
    logger.info(f"Task started: {task.name}[{task_id}]")

@task_postrun.connect
def task_completed(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **_):
    """Log when a task completes."""
    logger.info(f"Task completed: {task.name}[{task_id}] - Status: {state}")

@task_failure.connect
def task_failed(sender=None, task_id=None, exception=None, args=None, kwargs=None, traceback=None, einfo=None, **_):
    """Log when a task fails."""
    logger.error(f"Task failed: {sender.name}[{task_id}] - Error: {exception}")

# ----- Core tasks -----

@celery.task(bind=True, name='tasks.generate_spectrogram_task', max_retries=3, retry_backoff=True)
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
    try:
        # Update task state to processing
        self.update_state(state="PROCESSING", meta={'progress': 10})
        
        # Get file paths
        if output_path is None:
            output_path = appropriate_file(path, args)
            
        # Convert URL path to OS path (if not already converted)
        if path.startswith('home/'):
            os_path = utils.convert_path_to_os_specific(path)
        else:
            os_path = path
            
        # Update progress
        self.update_state(state="PROCESSING", meta={'progress': 30})
        
        # Generate the spectrogram
        success, output_file, error = generate_spectrogram(os_path, args, output_path)
        
        # Update progress
        self.update_state(state="PROCESSING", meta={'progress': 90})
        
        if success:
            logger.info(f"Task {self.request.id}: Successfully generated {output_file}")
            return {
                'status': 'success',
                'file_path': output_file,
                'original_path': path,
                'args': args
            }
        else:
            logger.error(f"Task {self.request.id}: Failed to generate {output_file}: {error}")
            return {
                'status': 'error',
                'error': error if error else 'Failed to generate spectrogram',
                'file_path': output_file
            }
            
    except Exception as e:
        logger.error(f"Task {self.request.id}: Error generating spectrogram: {str(e)}")
        logger.debug(traceback.format_exc())
        
        # Retry the task if appropriate
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying task {self.request.id} ({self.request.retries+1}/{self.max_retries})")
            raise self.retry(exc=e, countdown=2 ** self.request.retries)
            
        return {
            'status': 'error',
            'error': str(e),
            'path': path,
            'args': args
        }

@celery.task(bind=True, name='tasks.prefetch_spectrograms')
def prefetch_spectrograms(self, path, base_args, call_range):
    """
    Prefetch multiple spectrograms for a range of calls.
    
    Args:
        path: Path to the audio file
        base_args: Base arguments dict
        call_range: Tuple of (start_call, end_call)
    
    Returns:
        dict: Summary of prefetched items
    """
    start_call, end_call = call_range
    tasks = []
    
    for call in range(start_call, end_call + 1):
        # Create a copy of args with updated call number
        args = base_args.copy()
        args['call'] = str(call)
        
        # Add task to list
        tasks.append(generate_spectrogram_task.s(path, args))
    
    # Execute tasks as a group
    job = group(tasks)
    result = job.apply_async()
    
    # Return a summary
    return {
        'status': 'submitted',
        'total_tasks': len(tasks),
        'call_range': call_range,
        'path': path
    }