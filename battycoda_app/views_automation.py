import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .models import DetectionRun, DetectionResult, TaskBatch, Call, CallProbability, Task, Classifier

# Set up logging
logger = logging.getLogger("battycoda.views_automation")


@login_required
def automation_home_view(request):
    """Display the main automation dashboard"""
    profile = request.user.profile
    
    # Get recent detection runs for user's groups
    if profile.group:
        if profile.is_admin:
            recent_runs = DetectionRun.objects.filter(group=profile.group).order_by("-created_at")[:10]
        else:
            recent_runs = DetectionRun.objects.filter(
                group=profile.group, created_by=request.user
            ).order_by("-created_at")[:10]
    else:
        recent_runs = DetectionRun.objects.filter(created_by=request.user).order_by("-created_at")[:10]
    
    context = {
        "recent_runs": recent_runs,
    }
    
    return render(request, "automation/dashboard.html", context)


@login_required
def detection_run_list_view(request):
    """Display list of all detection runs"""
    profile = request.user.profile
    
    # Filter detection runs by group if the user is in a group
    if profile.group:
        if profile.is_admin:
            # Admin sees all runs in their group
            runs = DetectionRun.objects.filter(group=profile.group).order_by("-created_at")
        else:
            # Regular user only sees their own runs
            runs = DetectionRun.objects.filter(created_by=request.user).order_by("-created_at")
    else:
        # Fallback to showing only user's runs if no group is assigned
        runs = DetectionRun.objects.filter(created_by=request.user).order_by("-created_at")
    
    context = {
        "runs": runs,
    }
    
    return render(request, "automation/run_list.html", context)


@login_required
def detection_run_detail_view(request, run_id):
    """Display details of a specific detection run"""
    # Get the detection run by ID
    run = get_object_or_404(DetectionRun, id=run_id)
    
    # Check if the user has permission to view this run
    profile = request.user.profile
    if run.created_by != request.user and (not profile.group or run.group != profile.group):
        messages.error(request, "You don't have permission to view this detection run.")
        return redirect("battycoda_app:automation_home")
    
    # Get results with task ordering
    results = DetectionResult.objects.filter(detection_run=run).order_by("task__onset")
    
    # Get all call types for this species to use as table headers
    call_types = Call.objects.filter(species=run.batch.species).order_by("short_name")
    
    # Prepare the data for rendering
    results_with_probabilities = []
    for result in results:
        # Get all probabilities for this result
        probabilities = CallProbability.objects.filter(detection_result=result)
        
        # Create a dictionary mapping call type ID to probability
        prob_dict = {prob.call_id: prob.probability for prob in probabilities}
        
        # For each call type, get the probability (or default to 0)
        call_probs = []
        for call in call_types:
            call_probs.append({
                "call": call,
                "probability": prob_dict.get(call.id, 0.0)
            })
        
        # Add to results
        results_with_probabilities.append({
            "result": result,
            "task": result.task,
            "probabilities": call_probs
        })
    
    context = {
        "run": run,
        "call_types": call_types,
        "results": results_with_probabilities,
    }
    
    return render(request, "automation/run_detail.html", context)


@login_required
def create_detection_run_view(request, batch_id=None):
    """Create a new detection run for a specific batch"""
    if request.method == "POST":
        batch_id = request.POST.get("batch_id") or batch_id
        name = request.POST.get("name")
        algorithm_type = request.POST.get("algorithm_type", "highest_only")
        classifier_id = request.POST.get("classifier_id")
        
        if not batch_id:
            messages.error(request, "Batch ID is required")
            return redirect("battycoda_app:task_batch_list")
        
        # Get the batch
        batch = get_object_or_404(TaskBatch, id=batch_id)
        
        # Check if user has permission
        profile = request.user.profile
        if batch.created_by != request.user and (not profile.group or batch.group != profile.group):
            messages.error(request, "You don't have permission to create a detection run for this batch.")
            return redirect("battycoda_app:task_batch_list")
        
        # Get the classifier
        classifier = None
        if classifier_id:
            classifier = get_object_or_404(Classifier, id=classifier_id)
        else:
            # Try to get the default R-direct classifier
            try:
                classifier = Classifier.objects.get(name='R-direct Classifier')
                logger.info(f"Using default R-direct classifier")
            except Classifier.DoesNotExist:
                messages.error(request, "Default classifier not found. Please select a classifier.")
                return redirect("battycoda_app:create_detection_run", batch_id=batch_id)
        
        # Create the detection run
        try:
            run = DetectionRun.objects.create(
                name=name or f"Detection for {batch.name}",
                batch=batch,
                created_by=request.user,
                group=profile.group,
                algorithm_type=classifier.response_format,  # Use the classifier's response format
                classifier=classifier,
                status="pending",
                progress=0.0
            )
            
            # Launch the Celery task
            from .audio.tasks import run_call_detection
            run_call_detection.delay(run.id)
            
            # If AJAX request
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"success": True, "run_id": run.id})
            
            messages.success(request, "Detection run created successfully. Processing will begin shortly.")
            return redirect("battycoda_app:detection_run_detail", run_id=run.id)
            
        except Exception as e:
            logger.error(f"Error creating detection run: {str(e)}")
            
            # If AJAX request
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": str(e)})
            
            messages.error(request, f"Error creating detection run: {str(e)}")
            return redirect("battycoda_app:task_batch_detail", batch_id=batch_id)
    
    # For GET requests, show the form
    if batch_id:
        batch = get_object_or_404(TaskBatch, id=batch_id)
        
        # Check if user has permission
        profile = request.user.profile
        if batch.created_by != request.user and (not profile.group or batch.group != profile.group):
            messages.error(request, "You don't have permission to create a detection run for this batch.")
            return redirect("battycoda_app:task_batch_list")
        
        # Get available classifiers (group's classifiers and global classifiers)
        if profile.group:
            classifiers = Classifier.objects.filter(is_active=True).filter(
                models.Q(group=profile.group) | models.Q(group__isnull=True)
            ).order_by('name')
        else:
            classifiers = Classifier.objects.filter(is_active=True, group__isnull=True).order_by('name')
            
        logger.info(f"Found {classifiers.count()} classifiers for user {request.user.username} with group {profile.group}")
        
        # If no classifiers are available, show a message and redirect
        if not classifiers.exists():
            messages.error(request, "No classifiers available. Please contact an administrator.")
            return redirect("battycoda_app:task_batch_detail", batch_id=batch_id)
        
        context = {
            "batch": batch,
            "classifiers": classifiers,
            "default_classifier": classifiers.filter(name='R-direct Classifier').first()
        }
        
        return render(request, "automation/create_run.html", context)
    
    # If no batch_id provided, show list of available batches
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
    
    return render(request, "automation/select_batch.html", context)


@login_required
def detection_run_status_view(request, run_id):
    """AJAX view for checking status of a detection run"""
    # Get the detection run by ID
    run = get_object_or_404(DetectionRun, id=run_id)
    
    # Check if the user has permission to view this run
    profile = request.user.profile
    if run.created_by != request.user and (not profile.group or run.group != profile.group):
        return JsonResponse({"success": False, "error": "Permission denied"}, status=403)
    
    # Return the status
    return JsonResponse({
        "success": True,
        "status": run.status,
        "progress": run.progress,
        "error": run.error_message,
    })


@login_required
def apply_detection_results_view(request, run_id, task_id=None):
    """Apply detection results as task labels"""
    # Get the detection run by ID
    run = get_object_or_404(DetectionRun, id=run_id)
    
    # Check if the user has permission
    profile = request.user.profile
    if run.created_by != request.user and (not profile.group or run.group != profile.group):
        messages.error(request, "You don't have permission to apply detection results.")
        return redirect("battycoda_app:detection_run_list")
    
    # Check if the run is completed
    if run.status != "completed":
        messages.error(request, "Cannot apply results from an incomplete detection run.")
        return redirect("battycoda_app:detection_run_detail", run_id=run_id)
    
    # If task_id is provided, apply to a specific task
    if task_id:
        task = get_object_or_404(Task, id=task_id)
        
        # Check if the task belongs to this run's batch
        if task.batch_id != run.batch_id:
            messages.error(request, "Task does not belong to this detection run's batch.")
            return redirect("battycoda_app:detection_run_detail", run_id=run_id)
        
        # Get the detection result for this task
        try:
            result = DetectionResult.objects.get(detection_run=run, task=task)
            
            # Handle differently based on algorithm type
            if run.classifier and run.classifier.response_format == "highest_only":
                # For highest-only algorithm, we just need to get the non-zero probability
                top_probability = CallProbability.objects.filter(
                    detection_result=result, 
                    probability__gt=0
                ).first()
                
                if top_probability:
                    # Apply the label
                    task.label = top_probability.call.short_name
                    task.confidence = top_probability.probability
                    task.status = "completed"  # Mark as completed but not done
                    task.save()
                    
                    messages.success(request, f"Applied label '{top_probability.call.short_name}' to task.")
                else:
                    messages.error(request, "No probability data found for this task.")
            else:
                # For full probability algorithm, get the highest probability
                top_probability = CallProbability.objects.filter(
                    detection_result=result
                ).order_by("-probability").first()
                
                if top_probability:
                    # Apply the label
                    task.label = top_probability.call.short_name
                    task.confidence = top_probability.probability
                    task.status = "completed"  # Mark as completed but not done
                    task.save()
                    
                    messages.success(request, f"Applied label '{top_probability.call.short_name}' to task.")
                else:
                    messages.error(request, "No probability data found for this task.")
        except DetectionResult.DoesNotExist:
            messages.error(request, "No detection result found for this task.")
        
        return redirect("battycoda_app:detection_run_detail", run_id=run_id)
    
    # If no task_id, apply to all tasks in the batch with a threshold
    threshold = float(request.GET.get("threshold", 0.7))  # Default threshold of 0.7
    
    # Get all results for this run
    results = DetectionResult.objects.filter(detection_run=run)
    
    applied_count = 0
    skipped_count = 0
    
    for result in results:
        # Handle differently based on algorithm type
        if run.classifier and run.classifier.response_format == "highest_only":
            # For highest-only algorithm, we just need to get the non-zero probability
            top_probability = CallProbability.objects.filter(
                detection_result=result, 
                probability__gt=0
            ).first()
            
            if top_probability and top_probability.probability >= threshold:
                # Apply the label
                task = result.task
                task.label = top_probability.call.short_name
                task.confidence = top_probability.probability
                task.status = "completed"  # Mark as completed but not done
                task.save()
                applied_count += 1
            else:
                skipped_count += 1
        else:
            # For full probability algorithm, get the highest probability
            top_probability = CallProbability.objects.filter(
                detection_result=result
            ).order_by("-probability").first()
            
            if top_probability and top_probability.probability >= threshold:
                # Apply the label
                task = result.task
                task.label = top_probability.call.short_name
                task.confidence = top_probability.probability
                task.status = "completed"  # Mark as completed but not done
                task.save()
                applied_count += 1
            else:
                skipped_count += 1
    
    messages.success(
        request, 
        f"Applied {applied_count} labels from detection results. "
        f"Skipped {skipped_count} results below threshold ({threshold})."
    )
    
    return redirect("battycoda_app:detection_run_detail", run_id=run_id)