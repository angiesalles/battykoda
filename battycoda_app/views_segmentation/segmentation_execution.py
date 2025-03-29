"""
Views for executing automated segmentation tasks on recordings.
"""
from .views_common import *


@login_required
def auto_segment_recording_view(request, recording_id, algorithm_id=None):
    """Run automated segmentation on a recording"""
    recording = get_object_or_404(Recording, id=recording_id)

    # Check permission
    profile = request.user.profile
    if recording.created_by != request.user and (not profile.group or recording.group != profile.group):
        messages.error(request, "You don't have permission to segment this recording.")
        return redirect("battycoda_app:recording_detail", recording_id=recording_id)

    from ..models import Segmentation, SegmentationAlgorithm

    # Get available algorithms
    if profile.group and profile.is_admin:
        # Admin sees all algorithms plus group-specific ones
        # First get all global algorithms
        global_query = SegmentationAlgorithm.objects.filter(is_active=True, group__isnull=True)

        # Then get group-specific algorithms
        group_query = SegmentationAlgorithm.objects.filter(is_active=True, group=profile.group)

        # Get all the IDs of both queries
        global_ids = set(global_query.values_list("id", flat=True))
        group_ids = set(group_query.values_list("id", flat=True))

        # Combine the IDs without duplicates
        all_ids = global_ids.union(group_ids)

        # Now get all algorithms with these IDs in a single query
        algorithms = SegmentationAlgorithm.objects.filter(id__in=all_ids).order_by("name")
    else:
        # Regular user sees only global algorithms
        algorithms = SegmentationAlgorithm.objects.filter(is_active=True, group__isnull=True).order_by("name")

    # Get the selected algorithm
    if algorithm_id:
        # Use filter().first() instead of get() to avoid MultipleObjectsReturned error
        try:
            logger.info(f"GET: Auto-segment with algorithm_id={algorithm_id}, type={type(algorithm_id)}")
            algorithm = SegmentationAlgorithm.objects.filter(id=int(algorithm_id), is_active=True).first()
            if not algorithm:
                # Fallback to the first algorithm if specified one not found
                algorithm = algorithms.first()
                logger.warning(
                    f"Algorithm with ID {algorithm_id} not found, using first available: {algorithm.id} - {algorithm.name}"
                )
            else:
                logger.info(f"Selected algorithm: {algorithm.id} - {algorithm.name}")
        except Exception as e:
            logger.error(f"Error getting algorithm by ID: {str(e)}")
            algorithm = algorithms.first()
    else:
        # Use the first available algorithm (usually Standard Threshold)
        algorithm = algorithms.first()
        if algorithm:
            logger.info(f"Using default algorithm: {algorithm.id} - {algorithm.name}")

    # Check for existing segmentations, but we no longer need to warn since we support multiple segmentations
    try:
        # Get the count of existing segmentations for information purposes
        existing_segmentations_count = Segmentation.objects.filter(recording=recording).count()
        existing_segmentation = None
    except Exception:
        existing_segmentations_count = 0
        existing_segmentation = None

    if request.method == "POST":
        # Log the POST data for debugging
        logger.info(f"POST data: {dict(request.POST.items())}")

        # Get parameters from request
        algorithm_id = request.POST.get("algorithm")
        logger.info(f"Algorithm ID from POST: {algorithm_id!r}")
        min_duration_ms = request.POST.get("min_duration_ms", 10)
        smooth_window = request.POST.get("smooth_window", 3)
        threshold_factor = request.POST.get("threshold_factor", 0.5)

        # Get the algorithm by ID if specified
        if algorithm_id:
            try:
                # Debug logs
                logger.info(f"Auto-segment with algorithm_id={algorithm_id}, type={type(algorithm_id)}")
                # Use filter().first() instead of get() to avoid MultipleObjectsReturned error
                algorithm = SegmentationAlgorithm.objects.filter(id=int(algorithm_id), is_active=True).first()
                if not algorithm:
                    messages.error(request, f"Segmentation algorithm with ID {algorithm_id} not found.")
                    return redirect("battycoda_app:auto_segment_recording", recording_id=recording_id)
                logger.info(f"Selected algorithm: {algorithm.id} - {algorithm.name}")
            except Exception as e:
                logger.error(f"Error getting algorithm: {str(e)}")
                messages.error(request, f"Error selecting algorithm: {str(e)}")
                return redirect("battycoda_app:auto_segment_recording", recording_id=recording_id)

            # Check if user has access to this algorithm
            if algorithm.group and (not profile.group or algorithm.group != profile.group):
                messages.error(request, "You don't have permission to use this algorithm.")
                return redirect("battycoda_app:auto_segment_recording", recording_id=recording_id)
        else:
            # No algorithm selected - select the first algorithm as default
            algorithm = algorithms.first()
            if algorithm:
                logger.info(f"No algorithm explicitly selected, defaulting to: {algorithm.id} - {algorithm.name}")
            else:
                messages.error(request, "No segmentation algorithm was selected and no default algorithm is available.")
                return redirect("battycoda_app:auto_segment_recording", recording_id=recording_id)

        # Convert to appropriate types
        try:
            min_duration_ms = int(min_duration_ms)
            smooth_window = int(smooth_window)
            threshold_factor = float(threshold_factor)

            # Validate parameters
            if min_duration_ms < 1:
                raise ValueError("Minimum duration must be at least 1ms")
            if smooth_window < 1:
                raise ValueError("Smooth window must be at least 1 sample")
            if threshold_factor <= 0 or threshold_factor > 10:
                raise ValueError("Threshold factor must be between 0 and 10")
        except ValueError as e:
            messages.error(request, f"Invalid parameter: {str(e)}")
            return redirect("battycoda_app:segment_recording", recording_id=recording_id)

        # Start the segmentation task
        try:
            from celery import current_app

            # Check if debug visualization is requested
            debug_visualization = request.POST.get("debug_visualization", False) == "on"

            # Launch Celery task with debug visualization if requested
            task = current_app.send_task(
                algorithm.celery_task,
                args=[recording.id, min_duration_ms, smooth_window, threshold_factor, debug_visualization],
            )

            # Store task ID in session for status checking
            request.session[f"auto_segment_task_{recording_id}"] = task.id

            # Delete any existing segments for this recording
            with transaction.atomic():
                # Delete existing segments
                existing_count = Segment.objects.filter(recording=recording).count()
                if existing_count > 0:
                    logger.info(f"Deleting {existing_count} existing segments for recording {recording.id}")
                    Segment.objects.filter(recording=recording).delete()

                # Mark all existing segmentations as inactive
                Segmentation.objects.filter(recording=recording, is_active=True).update(is_active=False)

                # Create a new Segmentation entry to track this job
                segmentation = Segmentation.objects.create(
                    recording=recording,
                    name=f"{algorithm.name} {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    created_by=request.user,
                    algorithm=algorithm,
                    task_id=task.id,
                    status="in_progress",
                    progress=0,
                    is_active=True,
                    manually_edited=False,
                )

            # Set success message
            messages.success(
                request,
                f"Automated segmentation started using {algorithm.name}. This may take a few moments to complete.",
            )

            # Redirect to segmentation batch overview
            return redirect("battycoda_app:batch_segmentation")

        except Exception as e:
            logger.error(f"Error starting auto segmentation task: {str(e)}")
            logger.error(traceback.format_exc())

            # Set error message
            messages.error(request, f"Error starting segmentation: {str(e)}")

            # Redirect back to the auto segment form
            return redirect("battycoda_app:auto_segment_recording", recording_id=recording_id)

    # GET request - display form for configuring segmentation or return JSON if AJAX
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        # Return JSON with algorithm details for AJAX requests
        if algorithm:
            return JsonResponse(
                {
                    "success": True,
                    "algorithm_id": algorithm.id,
                    "algorithm_name": algorithm.name,
                    "algorithm_description": algorithm.description,
                    "algorithm_type": algorithm.get_algorithm_type_display(),
                    "min_duration_ms": algorithm.default_min_duration_ms,
                    "smooth_window": algorithm.default_smooth_window,
                    "threshold_factor": algorithm.default_threshold_factor,
                }
            )
        else:
            return JsonResponse({"success": False, "error": "Algorithm not found"}, status=404)

    # Regular GET request - render the form
    context = {
        "recording": recording,
        "algorithms": algorithms,
        "selected_algorithm": algorithm,
        "min_duration_ms": algorithm.default_min_duration_ms if algorithm else 10,
        "smooth_window": algorithm.default_smooth_window if algorithm else 3,
        "threshold_factor": algorithm.default_threshold_factor if algorithm else 0.5,
        "existing_segmentation": existing_segmentation,
    }

    return render(request, "recordings/auto_segment.html", context)


@login_required
def auto_segment_status_view(request, recording_id):
    """Check the status of an auto-segmentation task"""
    recording = get_object_or_404(Recording, id=recording_id)

    # Check permission
    profile = request.user.profile
    if recording.created_by != request.user and (not profile.group or recording.group != profile.group):
        return JsonResponse({"success": False, "error": "Permission denied"}, status=403)

    # Get task ID from session
    task_id = request.session.get(f"auto_segment_task_{recording_id}")

    if not task_id:
        # Try to get the segmentation from the database instead
        from ..models import Segmentation

        segmentation = Segmentation.objects.filter(recording_id=recording_id).first()

        if segmentation and segmentation.task_id:
            task_id = segmentation.task_id
        else:
            return JsonResponse(
                {"success": False, "status": "not_found", "message": "No active segmentation task found"}
            )

    try:
        from celery.result import AsyncResult

        from ..models import Segmentation

        # Get the segmentation from database
        segmentation = Segmentation.objects.filter(task_id=task_id).first()

        # Get task result
        result = AsyncResult(task_id)

        if result.ready():
            # Task is complete
            if result.successful():
                # Get result data
                task_result = result.get()

                # Success with segments
                if task_result.get("status") == "success":
                    segments_created = task_result.get("segments_created", 0)
                    message = f"Successfully created {segments_created} segments."

                    # Update segmentation status
                    if segmentation:
                        segmentation.status = "completed"
                        segmentation.progress = 100
                        segmentation.save()

                    # Clear task ID from session
                    if f"auto_segment_task_{recording_id}" in request.session:
                        del request.session[f"auto_segment_task_{recording_id}"]

                    # Prepare response with basic information
                    response_data = {
                        "success": True,
                        "status": "completed",
                        "message": message,
                        "segments_created": segments_created,
                        "result": task_result,
                    }

                    # Add debug visualization info if available
                    if task_result.get("debug_visualization"):
                        response_data["debug_visualization"] = task_result["debug_visualization"]

                    return JsonResponse(response_data)
                else:
                    # Task returned error status
                    error_message = task_result.get("message", "Unknown error in segmentation task")

                    # Update segmentation status
                    if segmentation:
                        segmentation.status = "failed"
                        segmentation.save()

                    # Clear task ID from session
                    if f"auto_segment_task_{recording_id}" in request.session:
                        del request.session[f"auto_segment_task_{recording_id}"]

                    return JsonResponse({"success": False, "status": "failed", "message": error_message})
            else:
                # Task failed with exception
                error_info = str(result.result)

                # Update segmentation status
                if segmentation:
                    segmentation.status = "failed"
                    segmentation.save()

                # Clear task ID from session
                if f"auto_segment_task_{recording_id}" in request.session:
                    del request.session[f"auto_segment_task_{recording_id}"]

                return JsonResponse(
                    {"success": False, "status": "failed", "message": f"Segmentation task failed: {error_info}"}
                )
        else:
            # Task is still running
            # Update segmentation status if it exists
            if segmentation and segmentation.status != "in_progress":
                segmentation.status = "in_progress"
                segmentation.save()

            return JsonResponse(
                {"success": True, "status": "in_progress", "message": "Segmentation is still processing..."}
            )

    except Exception as e:
        logger.error(f"Error checking segmentation task status: {str(e)}")
        logger.error(traceback.format_exc())

        return JsonResponse({"success": False, "status": "error", "message": f"Error checking task status: {str(e)}"})
