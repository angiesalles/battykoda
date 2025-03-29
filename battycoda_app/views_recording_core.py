"""
Core views for handling recording CRUD operations.
"""
from .views_common import *

# Set up logging
logger = logging.getLogger("battycoda.views_recording_core")


@login_required
def recording_list_view(request):
    """Display list of all recordings for the user's group"""
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
    }

    return render(request, "recordings/recording_list.html", context)


@login_required
def recording_detail_view(request, recording_id):
    """Display details of a specific recording and its segments"""
    # Get the recording by ID
    recording = get_object_or_404(Recording, id=recording_id)

    # Check if the user has permission to view this recording
    # Either they created it or they're in the same group
    profile = request.user.profile
    if recording.created_by != request.user and (not profile.group or recording.group != profile.group):
        messages.error(request, "You don't have permission to view this recording.")
        return redirect("battycoda_app:recording_list")

    # We no longer need to generate spectrograms since we're using waveform visualization
    # We also don't include segments in the recording detail view
    context = {
        "recording": recording,
    }

    return render(request, "recordings/recording_detail.html", context)


@login_required
def create_recording_view(request):
    """Handle creation of a new recording"""
    if request.method == "POST":
        form = RecordingForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            # Create the recording but don't save yet
            recording = form.save(commit=False)
            recording.created_by = request.user

            # Get user profile
            profile, created = UserProfile.objects.get_or_create(user=request.user)

            # Set group to user's current active group
            if profile.group:
                recording.group = profile.group
            else:
                # This is a critical issue - user must have a group
                messages.error(request, "You must be assigned to a group to create a recording")
                return redirect("battycoda_app:create_recording")

            # Save the recording
            recording.save()

            # Check if AJAX request
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {
                        "success": True,
                        "message": f"Successfully created recording: {recording.name}",
                        "redirect_url": reverse(
                            "battycoda_app:recording_detail", kwargs={"recording_id": recording.id}
                        ),
                    }
                )

            messages.success(request, f"Successfully created recording: {recording.name}")
            return redirect("battycoda_app:recording_detail", recording_id=recording.id)
        else:
            # Return JSON response for AJAX requests
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"success": False, "errors": form.errors})

    else:
        form = RecordingForm(user=request.user)

    context = {
        "form": form,
    }

    return render(request, "recordings/create_recording.html", context)


@login_required
def edit_recording_view(request, recording_id):
    """Edit an existing recording"""
    recording = get_object_or_404(Recording, id=recording_id)

    # Check if the user has permission to edit this recording
    profile = request.user.profile
    if recording.created_by != request.user and (
        not profile.group or recording.group != profile.group or not profile.is_admin
    ):
        messages.error(request, "You don't have permission to edit this recording.")
        return redirect("battycoda_app:recording_list")

    if request.method == "POST":
        form = RecordingForm(request.POST, request.FILES, instance=recording, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"Successfully updated recording: {recording.name}")
            return redirect("battycoda_app:recording_detail", recording_id=recording.id)
    else:
        form = RecordingForm(instance=recording, user=request.user)

    context = {
        "form": form,
        "recording": recording,
    }

    return render(request, "recordings/edit_recording.html", context)


@login_required
def delete_recording_view(request, recording_id):
    """Delete a recording"""
    recording = get_object_or_404(Recording, id=recording_id)

    # Check if the user has permission to delete this recording
    profile = request.user.profile
    if recording.created_by != request.user and (
        not profile.group or recording.group != profile.group or not profile.is_admin
    ):
        messages.error(request, "You don't have permission to delete this recording.")
        return redirect("battycoda_app:recording_list")

    if request.method == "POST":
        # Delete segments first
        Segment.objects.filter(recording=recording).delete()
        recording_name = recording.name
        recording.delete()
        messages.success(request, f"Successfully deleted recording: {recording_name}")
        return redirect("battycoda_app:recording_list")

    context = {
        "recording": recording,
    }

    return render(request, "recordings/delete_recording.html", context)
