"""
Celery configuration for BattyCoda.
This module initializes Celery and configures it to work with Flask.
"""
import os
from celery import Celery
import logging

# Configure logging
logger = logging.getLogger('battykoda.celery')

def make_celery(app=None):
    """
    Create a Celery instance configured to work with the Flask app.
    
    Args:
        app: Flask app instance (optional)
        
    Returns:
        Celery: Configured Celery instance
    """
    # Default broker URL (Redis)
    broker_url = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    result_backend = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    
    celery = Celery(
        'battykoda',
        broker=broker_url,
        result_backend=result_backend,
        include=['tasks']
    )
    
    # Configure Celery
    celery.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
        worker_prefetch_multiplier=1,  # Prefetch only one task per worker
        task_acks_late=True,  # Tasks are acknowledged after execution (safer)
        worker_max_tasks_per_child=200  # Restart worker after 200 tasks (prevent memory leaks)
    )
    
    # If Flask app is provided, integrate with it
    if app:
        celery.conf.update(app.config)
        
        class ContextTask(celery.Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)
        
        celery.Task = ContextTask
    
    logger.info(f"Initialized Celery with broker: {broker_url}")
    return celery

# Create default celery instance
celery = make_celery()

if __name__ == '__main__':
    celery.start()