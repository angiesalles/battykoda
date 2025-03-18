from django.apps import AppConfig


class BattycodaAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'battycoda_app'
    
    def ready(self):
        import battycoda_app.signals
