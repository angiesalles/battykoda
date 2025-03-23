import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, FileResponse

from .forms import TeamForm
from .models import TeamMembership, Task, TaskBatch

# Set up logging
logger = logging.getLogger('battycoda.views')

# Define the index view that redirects to the home page
def index(request):
    """Root URL - redirect to home view if logged in, or login page if not"""
    if request.user.is_authenticated:
        return redirect('battycoda_app:task_list')
    else:
        return redirect('battycoda_app:login')

# Basic and authentication views are now in views_auth.py

# Directory and navigation views are now in views_directory.py

# Species Management Views are now in views_species.py

# Project Management Views are now in views_project.py

# Team Management Views are now in views_team.py

# Import the invitation views
from .views_invitations import team_users_view, invite_user_view, accept_invitation_view

# Import task views
from .views_task import (
    task_list_view, task_detail_view, 
    task_batch_list_view, task_batch_detail_view,
    create_task_batch_view, create_task_view,
    task_annotation_view, wav_file_view,
    get_next_task_view, get_last_task_view, get_next_task_from_batch_view,
    task_status_view
)

# Import audio views
from .views_audio import spectrogram_view, audio_snippet_view

# Import directory views
from .views_directory import (
    home_view, user_directory_view, species_directory_view, subdirectory_view,
    species_info_view, create_directory_view, upload_file_view
)

# Import species views
from .views_species import (
    species_list_view, species_detail_view, create_species_view, edit_species_view,
    parse_calls_file_view
)

# Import project views
from .views_project import (
    project_list_view, project_detail_view, create_project_view, edit_project_view
)

# Import team views
from .views_team import (
    team_list_view, team_detail_view, create_team_view, edit_team_view,
    manage_team_members_view, switch_team_view, debug_teams_view
)

# Import auth views
from .views_auth import (
    login_view, register_view, logout_view, profile_view, edit_profile_view,
    password_reset_request, password_reset, request_login_code
)