"""
Views for managing individual recording segments (CRUD operations).
"""
import json

from .views_common import *


@login_required
def segment_recording_view(request, recording_id):
    """View for segmenting a recording (marking regions)"""
    recording = get_object_or_404(Recording, id=recording_id)

    # Check if the user has permission to edit this recording
    profile = request.user.profile
    if recording.created_by != request.user and (not profile.group or recording.group != profile.group):
        messages.error(request, "You don't have permission to segment this recording.")
        return redirect("battycoda_app:recording_list")

    # Get active segmentation for this recording
    try:
        active_segmentation = Segmentation.objects.get(recording=recording, is_active=True)

        # Get segments from the active segmentation
        segments = Segment.objects.filter(segmentation=active_segmentation).order_by("onset")

        # Add segmentation info to context
        segmentation_info = {
            "id": active_segmentation.id,
            "name": active_segmentation.name,
            "algorithm": active_segmentation.algorithm.name if active_segmentation.algorithm else "Manual",
            "created_at": active_segmentation.created_at,
            "manually_edited": active_segmentation.manually_edited,
        }
    except Segmentation.DoesNotExist:
        # No active segmentation, return empty queryset
        segments = Segment.objects.none()
        segmentation_info = None

        # Check if there are any segmentations at all
        if Segmentation.objects.filter(recording=recording).exists():
            # Activate the most recent segmentation
            latest_segmentation = Segmentation.objects.filter(recording=recording).order_by("-created_at").first()
            latest_segmentation.is_active = True
            latest_segmentation.save()

            # Redirect to refresh the page with the newly activated segmentation
            return redirect("battycoda_app:segment_recording", recording_id=recording.id)

    # Generate spectrogram if needed
    try:
        # Hash the recording file path for cache key
        file_hash = hashlib.md5(recording.wav_file.path.encode()).hexdigest()
        spectrogram_path = os.path.join(settings.MEDIA_ROOT, "spectrograms", "recordings", f"{file_hash}.png")

        # Check if spectrogram already exists
        if os.path.exists(spectrogram_path) and os.path.getsize(spectrogram_path) > 0:
            # Use existing spectrogram
            spectrogram_url = f"/media/spectrograms/recordings/{file_hash}.png"
        else:
            # Trigger generation
            from celery import current_app

            task = current_app.send_task(
                "battycoda_app.audio.task_modules.spectrogram_tasks.generate_recording_spectrogram", args=[recording.id]
            )
            # Use a placeholder until it's generated
            spectrogram_url = None
    except Exception as e:
        logger.error(f"Error checking/generating spectrogram: {str(e)}")
        spectrogram_url = None

    # Convert segments to JSON
    segments_json = []
    for segment in segments:
        segments_json.append({"id": segment.id, "onset": segment.onset, "offset": segment.offset})

    # Get all segmentations for the dropdown
    all_segmentations = Segmentation.objects.filter(recording=recording).order_by("-created_at")

    context = {
        "recording": recording,
        "segments": segments,
        "segments_json": json.dumps(segments_json),
        "spectrogram_url": spectrogram_url,
        "active_segmentation": segmentation_info,
        "all_segmentations": all_segmentations,
    }

    return render(request, "recordings/segment_recording.html", context)


@login_required
def add_segment_view(request, recording_id):
    """Add a segment to a recording via AJAX"""
    recording = get_object_or_404(Recording, id=recording_id)

    # Check if the user has permission
    profile = request.user.profile
    if recording.created_by != request.user and (not profile.group or recording.group != profile.group):
        return JsonResponse({"success": False, "error": "Permission denied"}, status=403)

    if request.method == "POST":
        form = SegmentForm(request.POST, recording=recording)
        if form.is_valid():
            segment = form.save(commit=False)
            segment.recording = recording
            segment.created_by = request.user
            segment.save(manual_edit=True)  # Mark as manually edited

            return JsonResponse(
                {
                    "success": True,
                    "segment": {
                        "id": segment.id,
                        "name": segment.name or f"Segment {segment.id}",
                        "onset": segment.onset,
                        "offset": segment.offset,
                        "duration": segment.duration,
                        "notes": segment.notes or "",
                    },
                }
            )
        else:
            return JsonResponse({"success": False, "errors": form.errors}, status=400)

    return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)


@login_required
def edit_segment_view(request, segment_id):
    """Edit a segment via AJAX"""
    segment = get_object_or_404(Segment, id=segment_id)
    recording = segment.recording

    # Check if the user has permission
    profile = request.user.profile
    if segment.created_by != request.user and (not profile.group or recording.group != profile.group):
        return JsonResponse({"success": False, "error": "Permission denied"}, status=403)

    if request.method == "POST":
        form = SegmentForm(request.POST, instance=segment, recording=recording)
        if form.is_valid():
            segment = form.save(commit=False)
            segment.save(manual_edit=True)  # Mark as manually edited

            return JsonResponse(
                {
                    "success": True,
                    "segment": {
                        "id": segment.id,
                        "name": segment.name or f"Segment {segment.id}",
                        "onset": segment.onset,
                        "offset": segment.offset,
                        "duration": segment.duration,
                        "notes": segment.notes or "",
                    },
                }
            )
        else:
            return JsonResponse({"success": False, "errors": form.errors}, status=400)

    return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)


@login_required
def delete_segment_view(request, segment_id):
    """Delete a segment via AJAX"""
    segment = get_object_or_404(Segment, id=segment_id)
    recording = segment.recording

    # Check if the user has permission
    profile = request.user.profile
    if segment.created_by != request.user and (not profile.group or recording.group != profile.group):
        return JsonResponse({"success": False, "error": "Permission denied"}, status=403)

    if request.method == "POST":
        # Get the segmentation to mark as manually edited
        segmentation = segment.segmentation
        if segmentation:
            segmentation.manually_edited = True
            segmentation.save()

        segment_id = segment.id
        segment.delete()
        return JsonResponse({"success": True, "segment_id": segment_id})

    return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)
