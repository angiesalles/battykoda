"""Views for applying detection results to segments.

Provides functionality to apply automated detection results to segments.
"""

from .common_imports import (  # Django imports; Models
    CallProbability,
    DetectionResult,
    DetectionRun,
    Segment,
    get_object_or_404,
    login_required,
    messages,
    redirect,
)


@login_required
def apply_detection_results_view(request, run_id, segment_id=None):
    """Apply classification results to segments."""
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
                top_probability = CallProbability.objects.filter(detection_result=result, probability__gt=0).first()

                if top_probability:
                    # We no longer apply call_type directly to segment model
                    # Instead just store the result in the DetectionResult

                    messages.success(
                        request, f"Classification found label '{top_probability.call.short_name}' for segment."
                    )
                else:
                    messages.error(request, "No probability data found for this segment.")
            else:
                # For full probability algorithm, get the highest probability
                top_probability = (
                    CallProbability.objects.filter(detection_result=result).order_by("-probability").first()
                )

                if top_probability:
                    # We no longer apply call_type directly to segment model
                    # Instead just store the result in the DetectionResult

                    messages.success(
                        request, f"Classification found label '{top_probability.call.short_name}' for segment."
                    )
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
            top_probability = CallProbability.objects.filter(detection_result=result, probability__gt=0).first()

            if top_probability and top_probability.probability >= threshold:
                # We no longer apply call_type directly to segment model
                # The classification results are already stored in DetectionResult
                applied_count += 1
            else:
                skipped_count += 1
        else:
            # For full probability algorithm, get the highest probability
            top_probability = CallProbability.objects.filter(detection_result=result).order_by("-probability").first()

            if top_probability and top_probability.probability >= threshold:
                # We no longer apply call_type directly to segment model
                # The classification results are already stored in DetectionResult
                applied_count += 1
            else:
                skipped_count += 1

    messages.success(
        request,
        f"Applied {applied_count} labels from classification results. "
        f"Skipped {skipped_count} results below threshold ({threshold}).",
    )

    return redirect("battycoda_app:detection_run_detail", run_id=run_id)
