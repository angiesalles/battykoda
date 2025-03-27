import csv
import logging
import pickle
import traceback
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

import numpy as np

from .audio.utils import process_pickle_file
from .forms import TaskBatchForm
from .models import Recording, Segment, Task, TaskBatch, UserProfile

# Set up logging
logger = logging.getLogger("battycoda.views_task_batch")


@login_required
def task_batch_list_view(request):
    """Display list of all task batches"""
    # Get user profile
    profile = request.user.profile

    # Filter batches by group if the user is in a group
    if profile.group:
        if profile.is_admin:
            # Admin sees all batches in their group
            batches = TaskBatch.objects.filter(group=profile.group).order_by("-created_at")
        else:
            # Regular user only sees their own batches
            batches = TaskBatch.objects.filter(created_by=request.user).order_by("-created_at")
    else:
        # Fallback to showing only user's batches if no group is assigned
        batches = TaskBatch.objects.filter(created_by=request.user).order_by("-created_at")

    context = {
        "batches": batches,
    }

    return render(request, "tasks/batch_list.html", context)


@login_required
def task_batch_detail_view(request, batch_id):
    """Display details of a specific task batch"""
    # Get the batch by ID
    batch = get_object_or_404(TaskBatch, id=batch_id)

    # Check if the user has permission to view this batch
    # Either they created it or they're in the same group
    profile = request.user.profile
    if batch.created_by != request.user and (not profile.group or batch.group != profile.group):
        messages.error(request, "You don't have permission to view this batch.")
        return redirect("battycoda_app:task_batch_list")

    # Get tasks with ascending ID order
    tasks = Task.objects.filter(batch=batch).order_by("id")  # Ordering by ID in ascending order

    context = {
        "batch": batch,
        "tasks": tasks,
    }

    return render(request, "tasks/batch_detail.html", context)


@login_required
def export_task_batch_view(request, batch_id):
    """Export task batch results to CSV"""
    # Get the batch by ID
    batch = get_object_or_404(TaskBatch, id=batch_id)

    # Check if the user has permission to export this batch
    # Either they created it or they're in the same group
    profile = request.user.profile
    if batch.created_by != request.user and (not profile.group or batch.group != profile.group):
        messages.error(request, "You don't have permission to export this batch.")
        return redirect("battycoda_app:task_batch_list")

    # Get tasks with ascending ID order
    tasks = Task.objects.filter(batch=batch).order_by("id")

    # Create HTTP response with CSV content type
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"taskbatch_{batch.id}_{batch.name.replace(' ', '_')}_{timestamp}.csv"
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    
    # Create CSV writer
    writer = csv.writer(response)
    
    # Write header row
    writer.writerow([
        "Task ID", 
        "Onset (s)", 
        "Offset (s)", 
        "Duration (s)",
        "Status", 
        "Label", 
        "Classification Result", 
        "Confidence", 
        "Notes",
        "WAV File", 
        "Species", 
        "Project", 
        "Created By", 
        "Created At", 
        "Updated At"
    ])
    
    # Write data rows
    for task in tasks:
        writer.writerow([
            task.id,
            task.onset,
            task.offset,
            task.offset - task.onset,
            task.status,
            task.label if task.label else "",
            task.classification_result if task.classification_result else "",
            task.confidence if task.confidence is not None else "",
            task.notes.replace('\n', ' ').replace('\r', '') if task.notes else "",
            task.wav_file_name,
            task.species.name,
            task.project.name,
            task.created_by.username,
            task.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            task.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        ])
    
    return response


@login_required
def create_task_batch_view(request):
    """Handle creation of a new task batch with WAV file upload, creating a recording and segments from pickle"""
    if request.method == "POST":
        form = TaskBatchForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            # Create the task batch but don't save yet
            batch = form.save(commit=False)
            batch.created_by = request.user

            # Get user profile
            profile, created = UserProfile.objects.get_or_create(user=request.user)

            # Set group to user's current active group
            if profile.group:
                batch.group = profile.group
            else:
                # This is a critical issue - user must have a group
                messages.error(request, "You must be assigned to a group to create a task batch")
                return redirect("battycoda_app:create_task_batch")

            # Get the WAV file from the form and set the wav_file_name from it
            if "wav_file" in request.FILES:
                # The wav_file field will be saved automatically when the form is saved
                wav_file = request.FILES["wav_file"]
                batch.wav_file_name = wav_file.name
            else:
                messages.error(request, "WAV file is required")
                return redirect("battycoda_app:create_task_batch")

            # Save the batch with files
            batch.save()
            
            # Create a Recording object from the WAV file
            recording = None
            segments_created = 0
            
            try:
                # Check if we have a pickle file
                pickle_file = request.FILES.get("pickle_file")
                
                # Use the utility function to create the recording and segments
                from .utils import create_recording_from_batch
                recording, segments_created = create_recording_from_batch(batch, pickle_file=pickle_file)
                
                if not recording:
                    messages.warning(request, "Task batch was created, but there was an error creating the recording")
                elif pickle_file and segments_created == 0:
                    messages.warning(request, f"Task batch and recording were created, but there was an error processing the pickle file")
            except Exception as e:
                logger.error(f"Error creating recording from task batch: {str(e)}")
                logger.error(traceback.format_exc())
                messages.warning(request, f"Task batch was created, but there was an error creating the recording: {str(e)}")

            # Check if AJAX request
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {
                        "success": True,
                        "message": "Successfully created task batch" + 
                                  (f" and recording with {segments_created} segments" if recording else ""),
                        "redirect_url": reverse("battycoda_app:task_batch_detail", kwargs={"batch_id": batch.id}),
                    }
                )

            # Prepare success message
            success_msg = "Successfully created task batch"
            if recording:
                success_msg += f" and recording"
                if segments_created > 0:
                    success_msg += f" with {segments_created} segments"
            
            messages.success(request, success_msg)
            return redirect("battycoda_app:task_batch_detail", batch_id=batch.id)
    else:
        form = TaskBatchForm(user=request.user)

    context = {
        "form": form,
    }

    return render(request, "tasks/create_batch.html", context)
