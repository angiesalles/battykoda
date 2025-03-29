import logging
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from .forms import GroupForm
from .models import GroupMembership, Task, TaskBatch

# Set up logging
logger = logging.getLogger("battycoda.views")


# Define the index view that redirects to the home page
def index(request):
    """Root URL - show dashboard if logged in, or login page if not"""
    if request.user.is_authenticated:
        # Get user profile
        profile = request.user.profile

        # Initialize context dictionary
        context = {}

        # Get recent task batches
        if profile.group:
            if profile.is_admin:
                # Admin sees all batches in their group
                recent_batches = TaskBatch.objects.filter(group=profile.group).order_by("-created_at")[:5]
            else:
                # Regular user only sees their own batches
                recent_batches = TaskBatch.objects.filter(created_by=request.user).order_by("-created_at")[:5]
        else:
            # Fallback to showing only user's batches if no group is assigned
            recent_batches = TaskBatch.objects.filter(created_by=request.user).order_by("-created_at")[:5]

        context["recent_batches"] = recent_batches

        # Get recent recordings
        from .models import Recording

        if profile.group:
            if profile.is_admin:
                # Admin sees all recordings in their group
                recent_recordings = Recording.objects.filter(group=profile.group).order_by("-created_at")[:5]
            else:
                # Regular user only sees their own recordings
                recent_recordings = Recording.objects.filter(created_by=request.user).order_by("-created_at")[:5]
        else:
            # Fallback to showing only user's recordings if no group is assigned
            recent_recordings = Recording.objects.filter(created_by=request.user).order_by("-created_at")[:5]

        context["recent_recordings"] = recent_recordings

        # Get recent classification runs
        from .models import DetectionRun

        if profile.group:
            if profile.is_admin:
                # Admin sees all runs in their group
                recent_runs = DetectionRun.objects.filter(group=profile.group).order_by("-created_at")[:5]
            else:
                # Regular user only sees their own runs
                recent_runs = DetectionRun.objects.filter(created_by=request.user).order_by("-created_at")[:5]
        else:
            # Fallback to showing only user's runs if no group is assigned
            recent_runs = DetectionRun.objects.filter(created_by=request.user).order_by("-created_at")[:5]

        context["recent_runs"] = recent_runs

        # Get recent species
        from .models import Species

        if profile.group:
            recent_species = Species.objects.filter(group=profile.group).order_by("-created_at")[:5]
        else:
            recent_species = Species.objects.filter(created_by=request.user).order_by("-created_at")[:5]

        context["recent_species"] = recent_species

        # Get recent projects
        from .models import Project

        if profile.group:
            recent_projects = Project.objects.filter(group=profile.group).order_by("-created_at")[:5]
        else:
            recent_projects = Project.objects.filter(created_by=request.user).order_by("-created_at")[:5]

        context["recent_projects"] = recent_projects

        # Get stats
        if profile.group:
            context["total_recordings"] = Recording.objects.filter(group=profile.group).count()
            context["total_batches"] = TaskBatch.objects.filter(group=profile.group).count()
            context["total_species"] = Species.objects.filter(group=profile.group).count()
            context["total_projects"] = Project.objects.filter(group=profile.group).count()

            # Get in-progress segmentations
            from .models import Segmentation

            context["active_segmentations"] = Segmentation.objects.filter(
                recording__group=profile.group, status__in=["pending", "in_progress"]
            ).count()

            # Get in-progress classifications
            context["active_classifications"] = DetectionRun.objects.filter(
                group=profile.group, status__in=["pending", "in_progress"]
            ).count()
        else:
            context["total_recordings"] = Recording.objects.filter(created_by=request.user).count()
            context["total_batches"] = TaskBatch.objects.filter(created_by=request.user).count()
            context["total_species"] = Species.objects.filter(created_by=request.user).count()
            context["total_projects"] = Project.objects.filter(created_by=request.user).count()

            # Get in-progress segmentations
            from .models import Segmentation

            context["active_segmentations"] = Segmentation.objects.filter(
                created_by=request.user, status__in=["pending", "in_progress"]
            ).count()

            # Get in-progress classifications
            context["active_classifications"] = DetectionRun.objects.filter(
                created_by=request.user, status__in=["pending", "in_progress"]
            ).count()

        return render(request, "dashboard.html", context)
    else:
        return redirect("battycoda_app:login")


# Basic and authentication views are now in views_auth.py

# Directory and navigation views are now in views_directory.py

# Species Management Views are now in views_species.py

# Project Management Views are now in views_project.py

# Group Management Views are now in views_group.py

# Import audio views
from .views_audio import audio_snippet_view, spectrogram_view

# Import auth views
from .views_auth import (
    edit_profile_view,
    login_view,
    logout_view,
    password_reset,
    password_reset_request,
    profile_view,
    register_view,
    request_login_code,
)

# Import group views
from .views_group import (
    create_group_view,
    edit_group_view,
    group_detail_view,
    group_list_view,
    manage_group_members_view,
    switch_group_view,
)

# Import the invitation views
from .views_invitations import accept_invitation_view, group_users_view, invite_user_view

# Import project views
from .views_project import create_project_view, edit_project_view, project_detail_view, project_list_view

# Import species views
from .views_species import (
    create_species_view,
    edit_species_view,
    parse_calls_file_view,
    species_detail_view,
    species_list_view,
)

# Import task views
from .views_task import (
    create_task_batch_view,
    create_task_view,
    get_last_task_view,
    get_next_task_from_batch_view,
    get_next_task_view,
    task_annotation_view,
    task_batch_detail_view,
    task_batch_list_view,
    task_detail_view,
    task_list_view,
    task_status_view,
    wav_file_view,
)

# Directory views have been removed
