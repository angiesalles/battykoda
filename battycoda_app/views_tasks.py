"""
Views for handling tasks and spectrograms.
"""
from .views_common import *

# Set up logging
logger = logging.getLogger("battycoda.views_tasks")


@login_required
def create_tasks_from_segments_view(request, recording_id):
    """Create tasks from all segments in a recording"""
    recording = get_object_or_404(Recording, id=recording_id)

    # Check if the user has permission
    profile = request.user.profile
    if recording.created_by != request.user and (not profile.group or recording.group != profile.group):
        messages.error(request, "You don't have permission to create tasks from this recording.")
        return redirect("battycoda_app:recording_detail", recording_id=recording.id)

    # Get all segments for this recording
    segments = Segment.objects.filter(recording=recording)

    if not segments.exists():
        messages.warning(request, "No segments found in this recording. Please add segments first.")
        return redirect("battycoda_app:segment_recording", recording_id=recording.id)

    # Create tasks for all segments
    tasks_created = 0
    with transaction.atomic():
        for segment in segments:
            if segment.task:
                # Skip segments that already have tasks
                continue

            try:
                # Create a task from this segment
                task = segment.create_task()
                tasks_created += 1
            except Exception as e:
                logger.error(f"Error creating task from segment {segment.id}: {str(e)}")
                messages.error(request, f"Error creating task for segment {segment.id}: {str(e)}")
                # Continue with other segments

    if tasks_created > 0:
        messages.success(request, f"Successfully created {tasks_created} tasks from segments.")
    else:
        messages.info(request, "No new tasks were created. All segments may already have associated tasks.")

    return redirect("battycoda_app:recording_detail", recording_id=recording.id)


@login_required
def recording_spectrogram_status_view(request, recording_id):
    """Check if the spectrogram for a recording has been generated"""
    recording = get_object_or_404(Recording, id=recording_id)

    # Check permission
    profile = request.user.profile
    if recording.created_by != request.user and (not profile.group or recording.group != profile.group):
        return JsonResponse({"success": False, "error": "Permission denied"}, status=403)

    try:
        # Hash the recording file path
        file_hash = hashlib.md5(recording.wav_file.path.encode()).hexdigest()
        spectrogram_path = os.path.join(settings.MEDIA_ROOT, "spectrograms", "recordings", f"{file_hash}.png")

        # Check if spectrogram exists
        if os.path.exists(spectrogram_path) and os.path.getsize(spectrogram_path) > 0:
            return JsonResponse(
                {"success": True, "status": "completed", "url": f"/media/spectrograms/recordings/{file_hash}.png"}
            )
        else:
            # Check if a task is in progress
            from celery import current_app
            from celery.result import AsyncResult

            # Try to get task ID from a potential in-progress task
            # Note: This is a simplification, in a real app you would store the task ID
            task_id = request.session.get(f"recording_spectrogram_task_{recording_id}")

            if task_id:
                task_result = AsyncResult(task_id)
                if task_result.ready():
                    if task_result.successful():
                        # Task completed, check again if file exists
                        if os.path.exists(spectrogram_path) and os.path.getsize(spectrogram_path) > 0:
                            return JsonResponse(
                                {
                                    "success": True,
                                    "status": "completed",
                                    "url": f"/media/spectrograms/recordings/{file_hash}.png",
                                }
                            )
                        else:
                            # Task completed but file not found
                            return JsonResponse(
                                {"success": False, "status": "error", "message": "Spectrogram generation failed."}
                            )
                    else:
                        # Task failed
                        return JsonResponse(
                            {"success": False, "status": "error", "message": "Spectrogram generation failed."}
                        )
                else:
                    # Task still in progress
                    return JsonResponse({"success": True, "status": "in_progress"})

            # No task found or task ID not stored, start a new task
            task = current_app.send_task(
                "battycoda_app.audio.tasks.generate_recording_spectrogram", args=[recording.id]
            )

            # Store task ID in session for status checks
            request.session[f"recording_spectrogram_task_{recording_id}"] = task.id

            return JsonResponse({"success": True, "status": "started", "task_id": task.id})
    except Exception as e:
        logger.error(f"Error checking spectrogram status: {str(e)}")
        logger.error(traceback.format_exc())
        return JsonResponse({"success": False, "status": "error", "message": str(e)})
