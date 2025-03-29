"""Views for creating tasks from detection runs.

Provides functionality to convert detection run results into manual tasks for review.
"""

from .common_imports import (  # Python standard library; Django imports; Models; Logging
    CallProbability,
    DetectionResult,
    DetectionRun,
    Task,
    TaskBatch,
    get_object_or_404,
    logger,
    login_required,
    messages,
    redirect,
    render,
    timezone,
    traceback,
    transaction,
)


@login_required
def create_task_batch_from_detection_run(request, run_id):
    """Create a task batch from a detection run's results for manual review and correction."""
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
                    detection_run=run,  # Link to the detection run
                )

                # Get all detection results from this run
                results = DetectionResult.objects.filter(detection_run=run)

                # Create tasks for each detection result's segment
                tasks_created = 0
                for result in results:
                    segment = result.segment

                    # Get the highest probability call type
                    top_probability = (
                        CallProbability.objects.filter(detection_result=result).order_by("-probability").first()
                    )

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
                        status="pending",
                    )

                    # Link the task back to the segment
                    segment.task = task
                    segment.save()

                    tasks_created += 1

                messages.success(request, f"Created task batch '{batch.name}' with {tasks_created} tasks for review.")

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
        "default_description": f"Manual review of classification run: {run.name}",
    }

    return render(request, "automation/create_task_batch.html", context)
