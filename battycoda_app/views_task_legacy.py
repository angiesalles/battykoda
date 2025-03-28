import logging
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect

from .models import Task
from .utils import convert_path_to_os_specific

# Set up logging
logger = logging.getLogger("battycoda.views_task_legacy")


@login_required
def wav_file_view(request, username, species, wav_path):
    """Legacy view for WAV file viewing - redirect to task creation"""
    # This view is kept for backward compatibility
    # Construct the full path
    full_path = f"home/{username}/{species}/{wav_path}"
    os_path = convert_path_to_os_specific(full_path)

    # Extract the project from the path (parent directory of the wav file)
    project = os.path.dirname(wav_path)

    # If there's no project, set it to the default
    if not project:
        project = "Default"

    # Create a new task if one doesn't exist
    task, created = Task.objects.get_or_create(
        wav_file_name=os.path.basename(wav_path),
        species=species,
        project=project,
        created_by=request.user,
        defaults={"onset": 0.0, "offset": 0.0, "status": "pending"},
    )

    # Redirect to the task annotation view
    messages.info(
        request,
        f"This interface is now task-based. A task has been {'created' if created else 'found'} for this WAV file.",
    )
    return redirect("battycoda_app:annotate_task", task_id=task.id)


@login_required
def task_status_view(request, task_id):
    """Handle checking Celery task status"""
    from .audio.views import task_status

    return task_status(request, task_id)
