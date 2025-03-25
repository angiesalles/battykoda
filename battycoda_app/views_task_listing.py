import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import TaskForm, TaskUpdateForm
from .models import Task, UserProfile

# Set up logging
logger = logging.getLogger("battycoda.views_task_listing")


@login_required
def task_list_view(request):
    """Display list of all tasks"""
    # Get user profile
    profile = request.user.profile

    # Filter tasks by group if the user is in a group
    if profile.group:
        if profile.is_admin:
            # Admin sees all tasks in their group
            tasks = Task.objects.filter(group=profile.group).order_by("-created_at")
        else:
            # Regular user only sees their own tasks
            tasks = Task.objects.filter(created_by=request.user).order_by("-created_at")
    else:
        # Fallback to showing only user's tasks if no group is assigned
        tasks = Task.objects.filter(created_by=request.user).order_by("-created_at")

    context = {
        "tasks": tasks,
    }

    return render(request, "tasks/task_list.html", context)


@login_required
def task_detail_view(request, task_id):
    """Display details of a specific task with option to update"""
    # Get the task without filtering by created_by
    task = get_object_or_404(Task, id=task_id)

    # Check if user has permission to view this task
    if task.created_by != request.user and (not request.user.profile.group or task.group != request.user.profile.group):
        messages.error(request, "You don't have permission to view this task.")
        return redirect("battycoda_app:task_list")

    # For editing, check if the user is the creator or a group admin
    can_edit = (task.created_by == request.user) or (
        request.user.profile.is_admin and task.group == request.user.profile.group
    )

    if request.method == "POST" and can_edit:
        form = TaskUpdateForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, "Task updated successfully.")
            return redirect("battycoda_app:task_detail", task_id=task.id)
    else:
        form = TaskUpdateForm(instance=task)

    context = {"task": task, "form": form, "can_edit": can_edit}

    return render(request, "tasks/task_detail.html", context)


@login_required
def create_task_view(request):
    """Handle creation of a single task"""
    if request.method == "POST":
        form = TaskForm(request.POST, user=request.user)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user

            # Always set group to user's active group
            task.group = request.user.profile.group
            task.save()

            messages.success(request, "Task created successfully.")
            return redirect("battycoda_app:task_list")
    else:
        form = TaskForm(user=request.user)

    context = {
        "form": form,
    }

    return render(request, "tasks/create_task.html", context)
