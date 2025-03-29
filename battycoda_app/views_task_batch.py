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
    writer.writerow(
        [
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
            "Updated At",
        ]
    )

    # Write data rows
    for task in tasks:
        writer.writerow(
            [
                task.id,
                task.onset,
                task.offset,
                task.offset - task.onset,
                task.status,
                task.label if task.label else "",
                task.classification_result if task.classification_result else "",
                task.confidence if task.confidence is not None else "",
                task.notes.replace("\n", " ").replace("\r", "") if task.notes else "",
                task.wav_file_name,
                task.species.name,
                task.project.name,
                task.created_by.username,
                task.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                task.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
            ]
        )

    return response


@login_required
def create_task_batch_view(request):
    """Direct creation of task batches now disabled - redirect to explanation"""
    # Create an informational message
    messages.info(
        request,
        "Task batches can now only be created from classification results. "
        "Please create a recording, segment it, run classification, and then create a task batch "
        "from the classification results for manual review.",
    )

    # Redirect to the task batch list
    return redirect("battycoda_app:task_batch_list")
