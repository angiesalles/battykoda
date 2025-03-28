import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ProjectForm
from .models import Project, Task, TaskBatch

# Set up logging
logger = logging.getLogger("battycoda.views_project")


@login_required
def project_list_view(request):
    """Display list of projects"""
    # Get the user's profile
    profile = request.user.profile

    # Filter projects by group if the user is in a group
    if profile.group:
        if profile.is_admin:
            # Admin sees all projects in their group
            project_list = Project.objects.filter(group=profile.group)
        else:
            # Regular user only sees projects in their group
            project_list = Project.objects.filter(group=profile.group)
    else:
        # If no group is assigned, show all projects (legacy behavior)
        project_list = Project.objects.all()

    context = {
        "project_list": project_list,
    }

    return render(request, "projects/project_list.html", context)


@login_required
def project_detail_view(request, project_id):
    """Display detail of a project"""
    project = get_object_or_404(Project, id=project_id)

    # Get tasks for this project
    tasks = Task.objects.filter(project=project)

    # Get batches for this project
    batches = TaskBatch.objects.filter(project=project)

    context = {
        "project": project,
        "tasks": tasks,
        "batches": batches,
    }

    return render(request, "projects/project_detail.html", context)


@login_required
def create_project_view(request):
    """Handle creation of a project"""
    if request.method == "POST":
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.created_by = request.user

            # Always set group to user's active group
            project.group = request.user.profile.group
            project.save()

            messages.success(request, "Project created successfully.")
            return redirect("battycoda_app:project_list")
    else:
        form = ProjectForm()

    context = {
        "form": form,
    }

    return render(request, "projects/create_project.html", context)


@login_required
def edit_project_view(request, project_id):
    """Handle editing of a project"""
    project = get_object_or_404(Project, id=project_id)

    # Only allow editing if the user is admin or in the same group
    if request.user.profile.is_admin or (request.user.profile.group and request.user.profile.group == project.group):
        if request.method == "POST":
            form = ProjectForm(request.POST, instance=project, user=request.user)
            if form.is_valid():
                form.save()

                messages.success(request, "Project updated successfully.")
                return redirect("battycoda_app:project_detail", project_id=project.id)
        else:
            form = ProjectForm(instance=project, user=request.user)

        context = {
            "form": form,
            "project": project,
        }

        return render(request, "projects/edit_project.html", context)
    else:
        messages.error(request, "You do not have permission to edit this project.")
        return redirect("battycoda_app:project_list")


@login_required
def delete_project_view(request, project_id):
    """Delete a project and its associated data"""
    project = get_object_or_404(Project, id=project_id)
    
    # Check if the user has permission to delete this project
    profile = request.user.profile
    if profile.is_admin or (profile.group and project.group == profile.group):
        # Get counts of related objects for context
        task_count = Task.objects.filter(project=project).count()
        batch_count = TaskBatch.objects.filter(project=project).count()
        
        # Check if deletion is allowed (no tasks or batches associated)
        has_dependencies = task_count > 0 or batch_count > 0
        
        if request.method == "POST":
            if has_dependencies:
                messages.error(request, "Cannot delete project with associated tasks or batches. Please remove these dependencies first.")
                return redirect("battycoda_app:delete_project", project_id=project.id)
                
            try:
                from django.db import transaction
                with transaction.atomic():
                    # Store name for the success message
                    project_name = project.name
                    
                    # Delete the project
                    project.delete()
                    
                    messages.success(request, f"Successfully deleted project: {project_name}")
                    return redirect("battycoda_app:project_list")
            except Exception as e:
                logger.error(f"Error deleting project {project.id}: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                messages.error(request, f"Failed to delete project: {str(e)}")
        
        context = {
            "project": project,
            "task_count": task_count,
            "batch_count": batch_count,
            "has_dependencies": has_dependencies,
        }
        
        return render(request, "projects/delete_project.html", context)
    else:
        messages.error(request, "You don't have permission to delete this project.")
        return redirect("battycoda_app:project_list")
