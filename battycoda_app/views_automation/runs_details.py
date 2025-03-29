"""Detail views for detection runs.

Provides views for displaying detailed information about detection runs.
"""

from .common_imports import (  # Django imports; Models
    Call,
    CallProbability,
    DetectionResult,
    DetectionRun,
    JsonResponse,
    get_object_or_404,
    login_required,
    messages,
    redirect,
    render,
)


@login_required
def detection_run_detail_view(request, run_id):
    """Display details of a specific classification run."""
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
            call_probs.append({"call": call, "probability": prob_dict.get(call.id, 0.0)})

        # Add to results
        results_with_probabilities.append({"result": result, "segment": result.segment, "probabilities": call_probs})

    context = {
        "run": run,
        "call_types": call_types,
        "results": results_with_probabilities,
    }

    return render(request, "automation/run_detail.html", context)


@login_required
def detection_run_status_view(request, run_id):
    """AJAX view for checking status of a detection run."""
    # Get the detection run by ID
    run = get_object_or_404(DetectionRun, id=run_id)

    # Check if the user has permission to view this run
    profile = request.user.profile
    if run.created_by != request.user and (not profile.group or run.group != profile.group):
        return JsonResponse({"success": False, "error": "Permission denied"}, status=403)

    # Return the status
    return JsonResponse(
        {
            "success": True,
            "status": run.status,
            "progress": run.progress,
            "error": run.error_message,
        }
    )
