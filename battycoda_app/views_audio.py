import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse

# Set up logging
logger = logging.getLogger("battycoda.views_audio")


@login_required
def spectrogram_view(request):
    """Handle spectrogram generation and serving"""
    from .audio.views import handle_spectrogram

    return handle_spectrogram(request)


@login_required
def audio_snippet_view(request):
    """Handle audio snippet generation and serving"""
    from .audio.views import handle_audio_snippet

    return handle_audio_snippet(request)


@login_required
def task_status(request, task_id):
    """
    Check the status of a task.

    Args:
        request: Django request
        task_id: ID of the Celery task

    Returns:
        JSON response with task status
    """
    from .audio.views import task_status as audio_task_status

    return audio_task_status(request, task_id)
