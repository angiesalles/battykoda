"""
Core views for managing recordings in BattyCoda.
"""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .forms import RecordingForm
from .models import Recording, Segment, Segmentation, UserProfile

# Set up logging
logger = logging.getLogger("battycoda.views_recording_core")


@login_required
def recording_list_view(request):
    """List all recordings for the current user's group"""
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if profile.group:
        recordings = Recording.objects.filter(group=profile.group).order_by("-created_at")
    else:
        recordings = Recording.objects.none()
    
    context = {
        "recordings": recordings,
    }
    
    return render(request, "recordings/recording_list.html", context)


@login_required
def recording_detail_view(request, recording_id):
    """Show details for a specific recording"""
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if not profile.group:
        messages.error(request, "You must be assigned to a group to view recordings")
        return redirect("battycoda_app:recording_list")
    
    recording = get_object_or_404(Recording, id=recording_id, group=profile.group)
    
    # Get active segmentation if any
    active_segmentation = Segmentation.objects.filter(
        recording=recording, is_active=True
    ).first()
    
    # Get segments if there is an active segmentation
    segments = []
    if active_segmentation:
        segments = Segment.objects.filter(
            recording=recording, segmentation=active_segmentation
        ).order_by("onset")
    
    # Get all segmentations for this recording
    segmentations = Segmentation.objects.filter(recording=recording).order_by("-created_at")
    
    context = {
        "recording": recording,
        "segmentations": segmentations,
        "active_segmentation": active_segmentation,
        "segments": segments,
    }
    
    return render(request, "recordings/recording_detail.html", context)


@login_required
def create_recording_view(request):
    """Create a new recording"""
    # Get user profile
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Check if user has a group
    if not profile.group:
        messages.error(request, "You must be assigned to a group to create recordings")
        return redirect("battycoda_app:recording_list")
    
    if request.method == "POST":
        form = RecordingForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            recording = form.save(commit=False)
            recording.group = profile.group
            recording.created_by = request.user
            recording.save()
            messages.success(request, f"Recording '{recording.name}' created successfully.")
            return redirect("battycoda_app:recording_detail", recording_id=recording.id)
    else:
        form = RecordingForm(user=request.user)
    
    context = {
        "form": form,
    }
    
    return render(request, "recordings/create_recording.html", context)


@login_required
def edit_recording_view(request, recording_id):
    """Edit an existing recording"""
    # Get user profile
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Check if user has a group
    if not profile.group:
        messages.error(request, "You must be assigned to a group to edit recordings")
        return redirect("battycoda_app:recording_list")
    
    # Get the recording (ensure it belongs to the user's group)
    recording = get_object_or_404(Recording, id=recording_id, group=profile.group)
    
    if request.method == "POST":
        form = RecordingForm(request.POST, request.FILES, instance=recording, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"Recording '{recording.name}' updated successfully.")
            return redirect("battycoda_app:recording_detail", recording_id=recording.id)
    else:
        form = RecordingForm(instance=recording, user=request.user)
    
    context = {
        "form": form,
        "recording": recording,
    }
    
    return render(request, "recordings/edit_recording.html", context)


@login_required
def delete_recording_view(request, recording_id):
    """Delete a recording"""
    # Get user profile
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Check if user has a group
    if not profile.group:
        messages.error(request, "You must be assigned to a group to delete recordings")
        return redirect("battycoda_app:recording_list")
    
    # Get the recording (ensure it belongs to the user's group)
    recording = get_object_or_404(Recording, id=recording_id, group=profile.group)
    
    if request.method == "POST":
        recording_name = recording.name
        recording.delete()
        messages.success(request, f"Recording '{recording_name}' deleted successfully.")
        return redirect("battycoda_app:recording_list")
    
    context = {
        "recording": recording,
    }
    
    return render(request, "recordings/delete_recording.html", context)