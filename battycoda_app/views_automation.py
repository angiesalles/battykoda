import logging
import traceback

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .models import Call, CallProbability, Classifier, DetectionResult, DetectionRun, Segment, Task, TaskBatch

# Set up logging
logger = logging.getLogger("battycoda.views_automation")


@login_required
def automation_home_view(request):
    """Display a list of classification runs with a button to start a new one"""
    try:
        profile = request.user.profile
        
        # Get all detection runs for user's groups, not just recent ones
        if profile.group:
            if profile.is_admin:
                runs = DetectionRun.objects.filter(group=profile.group).order_by("-created_at")
            else:
                runs = DetectionRun.objects.filter(
                    group=profile.group, created_by=request.user
                ).order_by("-created_at")
        else:
            runs = DetectionRun.objects.filter(created_by=request.user).order_by("-created_at")
        
        # Filter out runs that might have problematic data due to the migration
        valid_runs = []
        for run in runs:
            try:
                # Test if we can access required properties without errors
                _ = run.segmentation.recording.name
                valid_runs.append(run)
            except (AttributeError, Exception):
                # Skip this run if it causes errors
                logger.error(f"Skipping invalid run {run.id}: missing segmentation or recording")
                continue
                
        context = {
            "runs": valid_runs,
        }
        
        return render(request, "automation/dashboard.html", context)
    except Exception as e:
        logger.error(f"Error in automation_home_view: {str(e)}")
        messages.error(request, f"An error occurred: {str(e)}")
        # Provide a fallback response
        return render(request, "automation/dashboard.html", {"runs": []})


@login_required
def detection_run_list_view(request):
    """Display list of all detection runs - redirects to main automation view"""
    # We've combined this view with the main automation view
    return redirect("battycoda_app:automation_home")


@login_required
def detection_run_detail_view(request, run_id):
    """Display details of a specific classification run"""
    # Get the detection run by ID
    run = get_object_or_404(DetectionRun, id=run_id)
    
    # Check if the user has permission to view this run
    profile = request.user.profile
    if run.created_by != request.user and (not profile.group or run.group != profile.group):
        messages.error(request, "You don't have permission to view this classification run.")
        return redirect("battycoda_app:automation_home")
    
    # Get results with segment ordering
    results = DetectionResult.objects.filter(detection_run=run).order_by("segment__onset")
    
    # Get all call types for this species to use as table headers
    call_types = Call.objects.filter(species=run.segmentation.recording.species).order_by("short_name")
    
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
            "segment": result.segment,
            "probabilities": call_probs
        })
    
    context = {
        "run": run,
        "call_types": call_types,
        "results": results_with_probabilities,
    }
    
    return render(request, "automation/run_detail.html", context)


@login_required
def create_detection_run_view(request, segmentation_id=None):
    """Create a new classification run for a specific segmentation"""
    if request.method == "POST":
        segmentation_id = request.POST.get("segmentation_id") or segmentation_id
        name = request.POST.get("name")
        algorithm_type = request.POST.get("algorithm_type", "highest_only")
        classifier_id = request.POST.get("classifier_id")
        
        if not segmentation_id:
            messages.error(request, "Segmentation ID is required")
            return redirect("battycoda_app:recording_list")
        
        # Get the segmentation
        from .models import Segmentation
        segmentation = get_object_or_404(Segmentation, id=segmentation_id)
        
        # Check if user has permission
        profile = request.user.profile
        if segmentation.created_by != request.user and (not profile.group or segmentation.recording.group != profile.group):
            messages.error(request, "You don't have permission to create a classification run for this segmentation.")
            return redirect("battycoda_app:recording_list")
        
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
                return redirect("battycoda_app:create_detection_run", segmentation_id=segmentation_id)
        
        # Create the detection run
        try:
            run = DetectionRun.objects.create(
                name=name or f"Classification for {segmentation.recording.name}",
                segmentation=segmentation,
                created_by=request.user,
                group=profile.group,
                algorithm_type=classifier.response_format,  # Use the classifier's response format
                classifier=classifier,
                status="pending",
                progress=0.0
            )
            
            # Launch the appropriate Celery task based on the classifier
            if classifier.name == 'Dummy Classifier':
                # Use the dummy classifier task directly
                from .audio.tasks import run_dummy_classifier
                run_dummy_classifier.delay(run.id)
            else:
                # For other classifiers, use the standard task
                from .audio.tasks import run_call_detection
                run_call_detection.delay(run.id)
            
            # If AJAX request
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"success": True, "run_id": run.id})
            
            messages.success(request, "Classification run created successfully. Processing will begin shortly.")
            return redirect("battycoda_app:detection_run_detail", run_id=run.id)
            
        except Exception as e:
            logger.error(f"Error creating classification run: {str(e)}")
            
            # If AJAX request
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": str(e)})
            
            messages.error(request, f"Error creating classification run: {str(e)}")
            return redirect("battycoda_app:recording_detail", recording_id=segmentation.recording.id)
    
    # For GET requests, show the form
    if segmentation_id:
        from .models import Segmentation
        segmentation = get_object_or_404(Segmentation, id=segmentation_id)
        
        # Check if user has permission
        profile = request.user.profile
        if segmentation.created_by != request.user and (not profile.group or segmentation.recording.group != profile.group):
            messages.error(request, "You don't have permission to create a classification run for this segmentation.")
            return redirect("battycoda_app:recording_list")
        
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
            return redirect("battycoda_app:recording_detail", recording_id=segmentation.recording.id)
        
        context = {
            "segmentation": segmentation,
            "classifiers": classifiers,
            "default_classifier": classifiers.filter(name='R-direct Classifier').first()
        }
        
        return render(request, "automation/create_run.html", context)
    
    # If no segmentation_id provided, show list of available segmentations
    from .models import Segmentation
    profile = request.user.profile
    
    # Filter segmentations by group if the user is in a group
    if profile.group:
        if profile.is_admin:
            # Admin sees all segmentations in their group
            segmentations = Segmentation.objects.filter(
                recording__group=profile.group, 
                status='completed'
            ).order_by("-created_at")
        else:
            # Regular user only sees their own segmentations
            segmentations = Segmentation.objects.filter(
                created_by=request.user,
                status='completed'
            ).order_by("-created_at")
    else:
        # Fallback to showing only user's segmentations if no group is assigned
        segmentations = Segmentation.objects.filter(
            created_by=request.user,
            status='completed'
        ).order_by("-created_at")
    
    context = {
        "segmentations": segmentations,
    }
    
    return render(request, "automation/select_segmentation.html", context)


@login_required
def create_task_batch_from_detection_run(request, run_id):
    """Create a task batch from a detection run's results for manual review and correction"""
    # Get the detection run
    run = get_object_or_404(DetectionRun, id=run_id)
    
    # Check if the user has permission
    profile = request.user.profile
    if run.created_by != request.user and (not profile.group or run.group != profile.group):
        messages.error(request, "You don't have permission to create a task batch from this classification run.")
        return redirect("battycoda_app:automation_home")
    
    # Check if the run is completed
    if run.status != "completed":
        messages.error(request, "Cannot create a task batch from an incomplete classification run.")
        return redirect("battycoda_app:detection_run_detail", run_id=run_id)
    
    if request.method == "POST":
        # Get form data
        batch_name = request.POST.get("name") or f"Review of {run.name}"
        description = request.POST.get("description") or f"Manual review of classification run: {run.name}"
        
        try:
            with transaction.atomic():
                # Get the recording from the segmentation
                recording = run.segmentation.recording
                
                # Ensure batch name is unique by adding timestamp if needed
                from django.utils import timezone
                base_name = batch_name
                suffix = 1
                timestamp = timezone.now().strftime("%Y%m%d-%H%M%S")
                
                # First try with timestamp
                batch_name = f"{base_name} ({timestamp})"
                
                # If name still exists, add numeric suffix until unique
                while TaskBatch.objects.filter(name=batch_name, group=profile.group).exists():
                    batch_name = f"{base_name} ({timestamp}-{suffix})"
                    suffix += 1
                
                # Create the task batch with unique name
                batch = TaskBatch.objects.create(
                    name=batch_name,
                    description=description,
                    created_by=request.user,
                    wav_file_name=recording.wav_file.name,
                    wav_file=recording.wav_file,
                    species=recording.species,
                    project=recording.project,
                    group=profile.group,
                    detection_run=run  # Link to the detection run
                )
                
                # Get all detection results from this run
                results = DetectionResult.objects.filter(detection_run=run)
                
                # Create tasks for each detection result's segment
                tasks_created = 0
                for result in results:
                    segment = result.segment
                    
                    # Get the highest probability call type
                    top_probability = CallProbability.objects.filter(
                        detection_result=result
                    ).order_by('-probability').first()
                    
                    # Create a task for this segment
                    task = Task.objects.create(
                        wav_file_name=recording.wav_file.name,
                        onset=segment.onset,
                        offset=segment.offset,
                        species=recording.species,
                        project=recording.project,
                        batch=batch,
                        created_by=request.user,
                        group=profile.group,
                        # Use the highest probability call type as the initial label
                        label=top_probability.call.short_name if top_probability else None,
                        status="pending"
                    )
                    
                    # Link the task back to the segment
                    segment.task = task
                    segment.save()
                    
                    tasks_created += 1
                
                messages.success(
                    request, 
                    f"Created task batch '{batch.name}' with {tasks_created} tasks for review."
                )
                
                return redirect("battycoda_app:task_batch_detail", batch_id=batch.id)
                
        except Exception as e:
            logger.error(f"Error creating task batch from detection run: {str(e)}")
            logger.error(traceback.format_exc())
            messages.error(request, f"Error creating task batch: {str(e)}")
            return redirect("battycoda_app:detection_run_detail", run_id=run_id)
    
    # For GET requests, show the form
    context = {
        "run": run,
        "recording": run.segmentation.recording,
        "default_name": f"Review of {run.name}",
        "default_description": f"Manual review of classification run: {run.name}"
    }
    
    return render(request, "automation/create_task_batch.html", context)


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
def delete_detection_run_view(request, run_id):
    """Delete a classification run"""
    # Get the detection run by ID
    run = get_object_or_404(DetectionRun, id=run_id)
    
    # Check if the user has permission
    profile = request.user.profile
    if run.created_by != request.user and (not profile.group or run.group != profile.group):
        messages.error(request, "You don't have permission to delete this classification run.")
        return redirect("battycoda_app:automation_home")
    
    if request.method == "POST":
        # Delete all related results first
        CallProbability.objects.filter(detection_result__detection_run=run).delete()
        DetectionResult.objects.filter(detection_run=run).delete()
        
        # Store name for confirmation message
        run_name = run.name
        
        # Now delete the run itself
        run.delete()
        
        messages.success(request, f"Classification run '{run_name}' has been deleted.")
        return redirect("battycoda_app:automation_home")
    
    # For GET requests, show confirmation page
    return render(request, "automation/delete_run.html", {"run": run})


@login_required
def apply_detection_results_view(request, run_id, segment_id=None):
    """Apply classification results to segments"""
    # Get the detection run by ID
    run = get_object_or_404(DetectionRun, id=run_id)
    
    # Check if the user has permission
    profile = request.user.profile
    if run.created_by != request.user and (not profile.group or run.group != profile.group):
        messages.error(request, "You don't have permission to apply classification results.")
        return redirect("battycoda_app:automation_home")
    
    # Check if the run is completed
    if run.status != "completed":
        messages.error(request, "Cannot apply results from an incomplete classification run.")
        return redirect("battycoda_app:detection_run_detail", run_id=run_id)
    
    # If segment_id is provided, apply to a specific segment
    if segment_id:
        segment = get_object_or_404(Segment, id=segment_id)
        
        # Check if the segment belongs to this run's segmentation's recording
        if segment.recording_id != run.segmentation.recording_id:
            messages.error(request, "Segment does not belong to this classification run's recording.")
            return redirect("battycoda_app:detection_run_detail", run_id=run_id)
        
        # Get the detection result for this segment
        try:
            result = DetectionResult.objects.get(detection_run=run, segment=segment)
            
            # Handle differently based on algorithm type
            if run.classifier and run.classifier.response_format == "highest_only":
                # For highest-only algorithm, we just need to get the non-zero probability
                top_probability = CallProbability.objects.filter(
                    detection_result=result, 
                    probability__gt=0
                ).first()
                
                if top_probability:
                    # We no longer apply call_type directly to segment model
                    # Instead just store the result in the DetectionResult
                    
                    messages.success(request, f"Classification found label '{top_probability.call.short_name}' for segment.")
                else:
                    messages.error(request, "No probability data found for this segment.")
            else:
                # For full probability algorithm, get the highest probability
                top_probability = CallProbability.objects.filter(
                    detection_result=result
                ).order_by("-probability").first()
                
                if top_probability:
                    # We no longer apply call_type directly to segment model
                    # Instead just store the result in the DetectionResult
                    
                    messages.success(request, f"Classification found label '{top_probability.call.short_name}' for segment.")
                else:
                    messages.error(request, "No probability data found for this segment.")
        except DetectionResult.DoesNotExist:
            messages.error(request, "No classification result found for this segment.")
        
        return redirect("battycoda_app:detection_run_detail", run_id=run_id)
    
    # If no segment_id, apply to all segments with a threshold
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
                # We no longer apply call_type directly to segment model
                # The classification results are already stored in DetectionResult
                applied_count += 1
            else:
                skipped_count += 1
        else:
            # For full probability algorithm, get the highest probability
            top_probability = CallProbability.objects.filter(
                detection_result=result
            ).order_by("-probability").first()
            
            if top_probability and top_probability.probability >= threshold:
                # We no longer apply call_type directly to segment model
                # The classification results are already stored in DetectionResult
                applied_count += 1
            else:
                skipped_count += 1
    
    messages.success(
        request, 
        f"Applied {applied_count} labels from classification results. "
        f"Skipped {skipped_count} results below threshold ({threshold})."
    )
    
    return redirect("battycoda_app:detection_run_detail", run_id=run_id)