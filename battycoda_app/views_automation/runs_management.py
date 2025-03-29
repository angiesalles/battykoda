"""Management views for detection runs.

Provides views for creating, listing, and managing detection runs.
"""

from .common_imports import (  # Django imports; Models; Logging
    CallProbability,
    Classifier,
    DetectionResult,
    DetectionRun,
    JsonResponse,
    Segmentation,
    get_object_or_404,
    logger,
    login_required,
    messages,
    models,
    redirect,
    render,
)


@login_required
def automation_home_view(request):
    """Display a list of classification runs with a button to start a new one."""
    try:
        profile = request.user.profile

        # Get all detection runs for user's groups, not just recent ones
        if profile.group:
            if profile.is_admin:
                runs = DetectionRun.objects.filter(group=profile.group).order_by("-created_at")
            else:
                runs = DetectionRun.objects.filter(group=profile.group, created_by=request.user).order_by("-created_at")
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
    """Display list of all detection runs - redirects to main automation view."""
    # We've combined this view with the main automation view
    return redirect("battycoda_app:automation_home")


@login_required
def create_detection_run_view(request, segmentation_id=None):
    """Create a new classification run for a specific segmentation."""
    if request.method == "POST":
        segmentation_id = request.POST.get("segmentation_id") or segmentation_id
        name = request.POST.get("name")
        # Note: algorithm_type is not used here as classifier.response_format is used instead
        classifier_id = request.POST.get("classifier_id")

        if not segmentation_id:
            messages.error(request, "Segmentation ID is required")
            return redirect("battycoda_app:recording_list")

        # Get the segmentation
        segmentation = get_object_or_404(Segmentation, id=segmentation_id)

        # Check if user has permission
        profile = request.user.profile
        if segmentation.created_by != request.user and (
            not profile.group or segmentation.recording.group != profile.group
        ):
            messages.error(request, "You don't have permission to create a classification run for this segmentation.")
            return redirect("battycoda_app:recording_list")

        # Get the classifier
        classifier = None
        if classifier_id:
            classifier = get_object_or_404(Classifier, id=classifier_id)
        else:
            # Try to get the default R-direct classifier
            try:
                classifier = Classifier.objects.get(name="R-direct Classifier")
                logger.info("Using default R-direct classifier")
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
                progress=0.0,
            )

            # Launch the appropriate Celery task based on the classifier
            if classifier.name == "Dummy Classifier":
                # Use the dummy classifier task directly
                from battycoda_app.audio.tasks import run_dummy_classifier

                run_dummy_classifier.delay(run.id)
            else:
                # For other classifiers, use the standard task
                from battycoda_app.audio.tasks import run_call_detection

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
        segmentation = get_object_or_404(Segmentation, id=segmentation_id)

        # Check if user has permission
        profile = request.user.profile
        if segmentation.created_by != request.user and (
            not profile.group or segmentation.recording.group != profile.group
        ):
            messages.error(request, "You don't have permission to create a classification run for this segmentation.")
            return redirect("battycoda_app:recording_list")

        # Get available classifiers (group's classifiers and global classifiers)
        if profile.group:
            classifiers = (
                Classifier.objects.filter(is_active=True)
                .filter(models.Q(group=profile.group) | models.Q(group__isnull=True))
                .order_by("name")
            )
        else:
            classifiers = Classifier.objects.filter(is_active=True, group__isnull=True).order_by("name")

        logger.info(
            f"Found {classifiers.count()} classifiers for user {request.user.username} with group {profile.group}"
        )

        # If no classifiers are available, show a message and redirect
        if not classifiers.exists():
            messages.error(request, "No classifiers available. Please contact an administrator.")
            return redirect("battycoda_app:recording_detail", recording_id=segmentation.recording.id)

        context = {
            "segmentation": segmentation,
            "classifiers": classifiers,
            "default_classifier": classifiers.filter(name="R-direct Classifier").first(),
        }

        return render(request, "automation/create_run.html", context)

    # If no segmentation_id provided, show list of available segmentations
    profile = request.user.profile

    # Filter segmentations by group if the user is in a group
    if profile.group:
        if profile.is_admin:
            # Admin sees all segmentations in their group
            segmentations = Segmentation.objects.filter(recording__group=profile.group, status="completed").order_by(
                "-created_at"
            )
        else:
            # Regular user only sees their own segmentations
            segmentations = Segmentation.objects.filter(created_by=request.user, status="completed").order_by(
                "-created_at"
            )
    else:
        # Fallback to showing only user's segmentations if no group is assigned
        segmentations = Segmentation.objects.filter(created_by=request.user, status="completed").order_by("-created_at")

    context = {
        "segmentations": segmentations,
    }

    return render(request, "automation/select_segmentation.html", context)


@login_required
def delete_detection_run_view(request, run_id):
    """Delete a classification run."""
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
