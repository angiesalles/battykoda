"""
Application configuration for the audio module.
"""
from django.apps import AppConfig

class AudioConfig(AppConfig):
    name = 'battycoda_app.audio'
    verbose_name = 'BattyCoda Audio'
    
    def ready(self):
        # Import the tasks module to ensure tasks are registered
        from . import tasks