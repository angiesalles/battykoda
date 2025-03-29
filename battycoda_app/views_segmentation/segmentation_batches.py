"""
Views for managing batch segmentation operations.
"""
from .views_common import *


@login_required
def batch_segmentation_view(request):
    """Display a page for batch segmentation operations"""
    # Get user profile
    profile = request.user.profile

    # Filter recordings by group if the user is in a group
    if profile.group:
        if profile.is_admin:
            # Admin sees all recordings in their group
            recordings = Recording.objects.filter(group=profile.group).order_by("-created_at")
        else:
            # Regular user only sees their own recordings
            recordings = Recording.objects.filter(created_by=request.user).order_by("-created_at")
    else:
        # Fallback to showing only user's recordings if no group is assigned
        recordings = Recording.objects.filter(created_by=request.user).order_by("-created_at")

    context = {
        "recordings": recordings,
        "title": "Batch Segmentation",
        "page_description": "Apply segmentation strategies to multiple recordings and monitor segmentation jobs.",
    }

    return render(request, "recordings/batch_segmentation.html", context)


@login_required
def segmentation_jobs_status_view(request):
    """API endpoint to get the status of all segmentation jobs for the user"""
    # Get user profile
    profile = request.user.profile

    # Import the Segmentation model
    from ..models import Segmentation

    # Filter segmentations by user and group permissions
    if profile.group and profile.is_admin:
        # Admin sees all segmentations in their group
        segmentations = Segmentation.objects.filter(recording__group=profile.group).order_by("-created_at")
    else:
        # Regular user only sees their own segmentations
        segmentations = Segmentation.objects.filter(created_by=request.user).order_by("-created_at")

    # Check if any segmentations have pending task status that we should update
    if segmentations.filter(status__in=["pending", "in_progress"]).exists():
        from celery.result import AsyncResult

        for segmentation in segmentations.filter(status__in=["pending", "in_progress"]):
            # Only process if there's a task_id
            if not segmentation.task_id:
                continue

            try:
                # Get task result
                result = AsyncResult(segmentation.task_id)

                if result.ready():
                    if result.successful():
                        # Get result data
                        task_result = result.get()

                        # Success with segments
                        if task_result.get("status") == "success":
                            segments_created = task_result.get("segments_created", 0)
                            segmentation.status = "completed"
                            segmentation.progress = 100
                            segmentation.save()
                        else:
                            # Task returned error status
                            error_message = task_result.get("message", "Unknown error in segmentation task")
                            segmentation.status = "failed"
                            segmentation.save()
                    else:
                        # Task failed with exception
                        error_info = str(result.result)
                        segmentation.status = "failed"
                        segmentation.save()
            except Exception as e:
                logger.error(f"Error updating segmentation status for segmentation {segmentation.id}: {str(e)}")
                # Don't update the status in case of error

    # Format the segmentations for the response
    formatted_jobs = []
    for segmentation in segmentations[:20]:  # Limit to 20 most recent segmentations
        # Count segments
        segments_count = segmentation.recording.segments.count()

        # Basic job information
        formatted_job = {
            "id": segmentation.id,
            "recording_id": segmentation.recording.id,
            "recording_name": segmentation.recording.name,
            "name": segmentation.name,
            "status": segmentation.status,
            "progress": segmentation.progress,
            "start_time": segmentation.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "segments_created": segments_count,
            "algorithm_name": segmentation.algorithm.name if segmentation.algorithm else "Manual Import",
            "algorithm_type": segmentation.algorithm.get_algorithm_type_display()
            if segmentation.algorithm
            else "Manual",
            "view_url": reverse("battycoda_app:segment_recording", kwargs={"recording_id": segmentation.recording.id}),
            "retry_url": reverse(
                "battycoda_app:auto_segment_recording", kwargs={"recording_id": segmentation.recording.id}
            ),
            "is_processing": segmentation.is_processing,
            "manually_edited": segmentation.manually_edited,
            "is_active": segmentation.is_active,
        }

        # Check for debug visualization
        debug_path = os.path.join(settings.MEDIA_ROOT, "segmentation_debug")
        if os.path.exists(debug_path):
            # Look for debug images associated with this recording
            debug_pattern = f"segmentation_debug_{segmentation.recording.id}_*.png"
            debug_files = []
            for file in os.listdir(debug_path):
                if fnmatch.fnmatch(file, debug_pattern):
                    debug_files.append(file)

            # Sort by newest first (based on filename timestamp)
            debug_files.sort(reverse=True)

            # If we found any debug visualizations, add the URL to the most recent one
            if debug_files:
                formatted_job["debug_visualization"] = {"url": f"/media/segmentation_debug/{debug_files[0]}"}

        formatted_jobs.append(formatted_job)

    return JsonResponse({"success": True, "jobs": formatted_jobs})
