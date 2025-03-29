"""
Views for managing segmentation configuration settings.
"""
from .views_common import *


@login_required
def activate_segmentation_view(request, segmentation_id):
    """Activate a segmentation and deactivate all others for the same recording"""
    # Get the segmentation to activate
    segmentation = get_object_or_404(Segmentation, id=segmentation_id)
    recording = segmentation.recording

    # Check if the user has permission to edit this recording
    profile = request.user.profile
    if recording.created_by != request.user and (not profile.group or recording.group != profile.group):
        messages.error(request, "You don't have permission to modify segmentations for this recording.")
        return redirect("battycoda_app:recording_list")

    # Deactivate all segmentations for this recording
    Segmentation.objects.filter(recording=recording).update(is_active=False)

    # Activate the requested segmentation
    segmentation.is_active = True
    segmentation.save()

    # Handle AJAX requests
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"success": True, "message": f"Activated segmentation: {segmentation.name}"})

    # Redirect back to the recording's segmentation view
    messages.success(request, f"Activated segmentation: {segmentation.name}")
    return redirect("battycoda_app:segment_recording", recording_id=recording.id)
