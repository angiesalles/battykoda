import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect

from .models import Task, TaskBatch

# Set up logging
logger = logging.getLogger("battycoda.views_task_navigation")


@login_required
def get_next_task_from_batch_view(request, batch_id):
    """Get the next undone task from a specific batch and redirect to the annotation interface."""
    # Get the batch
    batch = get_object_or_404(TaskBatch, id=batch_id)

    # Get user profile and group
    profile = request.user.profile

    # Check if user has access to this batch
    if profile.group and batch.group == profile.group:
        # User has access via group membership
        pass
    elif batch.created_by == request.user:
        # User created the batch
        pass
    else:
        # User doesn't have access to this batch
        messages.error(request, "You don't have permission to annotate tasks from this batch.")
        return redirect("battycoda_app:task_batch_list")

    # Find the first undone task from this batch
    next_task = Task.objects.filter(batch=batch, is_done=False).order_by("created_at").first()

    if next_task:
        logger.info(f"Selected next task #{next_task.id} from batch #{batch.id}")
        # Redirect to the annotation interface with the task ID
        return redirect("battycoda_app:annotate_task", task_id=next_task.id)
    else:
        # No undone tasks found in this batch
        messages.info(request, f'No undone tasks found in batch "{batch.name}". All tasks in this batch are completed.')
        return redirect("battycoda_app:task_batch_detail", batch_id=batch.id)


@login_required
def get_next_task_view(request):
    """Get the next undone task and redirect to the annotation interface,
    preferentially selecting from the same batch as the last completed task."""
    # Get user profile and group
    profile = request.user.profile

    # Initialize query for tasks that aren't done yet
    tasks_query = Task.objects.filter(is_done=False)

    # If user has a group, include group tasks
    if profile.group:
        # Look for tasks from the user's group
        tasks_query = tasks_query.filter(group=profile.group)
    else:
        # Only look at user's own tasks if not in a group
        tasks_query = tasks_query.filter(created_by=request.user)

    # Try to find the most recently completed task to check its batch
    recent_tasks = Task.objects.filter(is_done=True)

    # Filter recent tasks by group or user
    if profile.group:
        recent_tasks = recent_tasks.filter(group=profile.group)
    else:
        recent_tasks = recent_tasks.filter(created_by=request.user)

    # Get the most recently updated task
    recent_task = recent_tasks.order_by("-updated_at").first()

    # If we found a recent task and it has a batch, preferentially get tasks from that batch
    if recent_task and recent_task.batch:
        logger.info(f"Looking for next task from same batch as recently completed task #{recent_task.id}")

        # Look for undone tasks from the same batch
        same_batch_tasks = tasks_query.filter(batch=recent_task.batch)
        next_task = same_batch_tasks.order_by("created_at").first()

        if next_task:
            logger.info(f"Found task #{next_task.id} from the same batch #{recent_task.batch.id}")
            return redirect("battycoda_app:annotate_task", task_id=next_task.id)
        else:
            logger.info(f"No more undone tasks in batch #{recent_task.batch.id}")

    # Fall back to the regular selection if no suitable task found from the same batch
    task = tasks_query.order_by("created_at").first()

    if task:
        logger.info(
            f"Selected next task #{task.id}" + (f" from batch #{task.batch.id}" if task.batch else " (no batch)")
        )
        # Redirect to the annotation interface with the task ID
        return redirect("battycoda_app:annotate_task", task_id=task.id)
    else:
        # No undone tasks found
        messages.info(request, "No undone tasks found. Please create new tasks or task batches.")
        return redirect("battycoda_app:task_list")


@login_required
def get_last_task_view(request):
    """Get the last task the user worked on (most recently updated) and redirect to it"""
    # Get user profile and group
    profile = request.user.profile

    # Initialize query for tasks
    tasks_query = Task.objects.all()

    # If user has a group, include group tasks
    if profile.group:
        # Look for tasks from the user's group
        tasks_query = tasks_query.filter(group=profile.group)
    else:
        # Only look at user's own tasks if not in a group
        tasks_query = tasks_query.filter(created_by=request.user)

    # Get the most recently updated task
    task = tasks_query.order_by("-updated_at").first()

    if task:
        # Redirect to the annotation interface with the task ID
        return redirect("battycoda_app:annotate_task", task_id=task.id)
    else:
        # No tasks found
        messages.info(request, "No tasks found. Please create new tasks or task batches.")
        return redirect("battycoda_app:task_list")
