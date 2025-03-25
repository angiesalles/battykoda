import hashlib
import logging
import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .audio.tasks import generate_recording_spectrogram
from .audio.utils import process_pickle_file
from .forms import RecordingForm, SegmentForm, SegmentFormSetFactory
from .models import Recording, Segment, UserProfile

# Set up logging
logger = logging.getLogger("battycoda.views_recordings")


@login_required
def recording_list_view(request):
    """Display list of all recordings for the user's team"""
    # Get user profile
    profile = request.user.profile

    # Filter recordings by team if the user is in a team
    if profile.team:
        if profile.is_admin:
            # Admin sees all recordings in their team
            recordings = Recording.objects.filter(team=profile.team).order_by("-created_at")
        else:
            # Regular user only sees their own recordings
            recordings = Recording.objects.filter(created_by=request.user).order_by("-created_at")
    else:
        # Fallback to showing only user's recordings if no team is assigned
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
    # Either they created it or they're in the same team
    profile = request.user.profile
    if recording.created_by != request.user and (not profile.team or recording.team != profile.team):
        messages.error(request, "You don't have permission to view this recording.")
        return redirect("battycoda_app:recording_list")

    # Get segments ordered by onset time
    segments = Segment.objects.filter(recording=recording).order_by("onset")

    # Get spectrogram for the recording
    # Trigger async generation or get cached version
    try:
        # Hash the recording file path for cache key
        file_hash = hashlib.md5(recording.wav_file.path.encode()).hexdigest()
        spectrogram_path = os.path.join(settings.MEDIA_ROOT, 'spectrograms', 'recordings', f"{file_hash}.png")
        
        # Check if spectrogram already exists
        if os.path.exists(spectrogram_path) and os.path.getsize(spectrogram_path) > 0:
            # Use existing spectrogram
            spectrogram_url = f"/media/spectrograms/recordings/{file_hash}.png"
        else:
            # Trigger generation
            from celery import current_app
            task = current_app.send_task(
                "battycoda_app.audio.tasks.generate_recording_spectrogram", args=[recording.id]
            )
            # Set to None until it's generated
            spectrogram_url = None
    except Exception as e:
        logger.error(f"Error checking/generating spectrogram: {str(e)}")
        spectrogram_url = None

    context = {
        "recording": recording,
        "segments": segments,
        "spectrogram_url": spectrogram_url,
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

            # Set team to user's current active team
            if profile.team:
                recording.team = profile.team
            else:
                # This is a critical issue - user must have a team
                messages.error(request, "You must be assigned to a team to create a recording")
                return redirect("battycoda_app:create_recording")

            # Save the recording
            recording.save()

            # Check if AJAX request
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {
                        "success": True,
                        "message": f"Successfully created recording: {recording.name}",
                        "redirect_url": reverse("battycoda_app:recording_detail", kwargs={"recording_id": recording.id}),
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
    if recording.created_by != request.user and (not profile.team or recording.team != profile.team or not profile.is_admin):
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
    if recording.created_by != request.user and (not profile.team or recording.team != profile.team or not profile.is_admin):
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


@login_required
def segment_recording_view(request, recording_id):
    """View for segmenting a recording (marking regions)"""
    recording = get_object_or_404(Recording, id=recording_id)

    # Check if the user has permission to edit this recording
    profile = request.user.profile
    if recording.created_by != request.user and (not profile.team or recording.team != profile.team):
        messages.error(request, "You don't have permission to segment this recording.")
        return redirect("battycoda_app:recording_list")

    # Get existing segments
    segments = Segment.objects.filter(recording=recording).order_by("onset")

    # Generate spectrogram if needed
    try:
        # Hash the recording file path for cache key
        file_hash = hashlib.md5(recording.wav_file.path.encode()).hexdigest()
        spectrogram_path = os.path.join(settings.MEDIA_ROOT, 'spectrograms', 'recordings', f"{file_hash}.png")
        
        # Check if spectrogram already exists
        if os.path.exists(spectrogram_path) and os.path.getsize(spectrogram_path) > 0:
            # Use existing spectrogram
            spectrogram_url = f"/media/spectrograms/recordings/{file_hash}.png"
        else:
            # Trigger generation
            from celery import current_app
            task = current_app.send_task(
                "battycoda_app.audio.tasks.generate_recording_spectrogram", args=[recording.id]
            )
            # Use a placeholder until it's generated
            spectrogram_url = None
    except Exception as e:
        logger.error(f"Error checking/generating spectrogram: {str(e)}")
        spectrogram_url = None

    context = {
        "recording": recording,
        "segments": segments,
        "spectrogram_url": spectrogram_url,
    }

    return render(request, "recordings/segment_recording.html", context)


@login_required
def add_segment_view(request, recording_id):
    """Add a segment to a recording via AJAX"""
    recording = get_object_or_404(Recording, id=recording_id)

    # Check if the user has permission
    profile = request.user.profile
    if recording.created_by != request.user and (not profile.team or recording.team != profile.team):
        return JsonResponse({"success": False, "error": "Permission denied"}, status=403)

    if request.method == "POST":
        form = SegmentForm(request.POST, recording=recording)
        if form.is_valid():
            segment = form.save(commit=False)
            segment.recording = recording
            segment.created_by = request.user
            segment.save()
            
            return JsonResponse({
                "success": True,
                "segment": {
                    "id": segment.id,
                    "name": segment.name or f"Segment {segment.id}",
                    "onset": segment.onset,
                    "offset": segment.offset,
                    "duration": segment.duration(),
                    "call_type": segment.call_type.short_name if segment.call_type else "Unclassified"
                }
            })
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
    if segment.created_by != request.user and (not profile.team or recording.team != profile.team):
        return JsonResponse({"success": False, "error": "Permission denied"}, status=403)

    if request.method == "POST":
        form = SegmentForm(request.POST, instance=segment, recording=recording)
        if form.is_valid():
            segment = form.save()
            
            return JsonResponse({
                "success": True,
                "segment": {
                    "id": segment.id,
                    "name": segment.name or f"Segment {segment.id}",
                    "onset": segment.onset,
                    "offset": segment.offset,
                    "duration": segment.duration(),
                    "call_type": segment.call_type.short_name if segment.call_type else "Unclassified"
                }
            })
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
    if segment.created_by != request.user and (not profile.team or recording.team != profile.team):
        return JsonResponse({"success": False, "error": "Permission denied"}, status=403)

    if request.method == "POST":
        segment_id = segment.id
        segment.delete()
        return JsonResponse({"success": True, "segment_id": segment_id})
    
    return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)


@login_required
def create_tasks_from_segments_view(request, recording_id):
    """Create tasks from all segments in a recording"""
    recording = get_object_or_404(Recording, id=recording_id)

    # Check if the user has permission
    profile = request.user.profile
    if recording.created_by != request.user and (not profile.team or recording.team != profile.team):
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
    if recording.created_by != request.user and (not profile.team or recording.team != profile.team):
        return JsonResponse({"success": False, "error": "Permission denied"}, status=403)
    
    try:
        # Hash the recording file path
        file_hash = hashlib.md5(recording.wav_file.path.encode()).hexdigest()
        spectrogram_path = os.path.join(settings.MEDIA_ROOT, 'spectrograms', 'recordings', f"{file_hash}.png")
        
        # Check if spectrogram exists
        if os.path.exists(spectrogram_path) and os.path.getsize(spectrogram_path) > 0:
            return JsonResponse({
                "success": True,
                "status": "completed",
                "url": f"/media/spectrograms/recordings/{file_hash}.png"
            })
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
                        # Task completed, check if file exists now
                        if os.path.exists(spectrogram_path) and os.path.getsize(spectrogram_path) > 0:
                            return JsonResponse({
                                "success": True,
                                "status": "completed",
                                "url": f"/media/spectrograms/recordings/{file_hash}.png"
                            })
                        else:
                            # Task completed but file not found, retry
                            task = current_app.send_task(
                                "battycoda_app.audio.tasks.generate_recording_spectrogram", args=[recording.id]
                            )
                            request.session[f"recording_spectrogram_task_{recording_id}"] = task.id
                            return JsonResponse({"success": True, "status": "processing"})
                    else:
                        # Task failed
                        return JsonResponse({"success": False, "status": "failed", "error": str(task_result.result)})
                else:
                    # Task still in progress
                    return JsonResponse({"success": True, "status": "processing"})
            else:
                # No task in progress, start one
                task = current_app.send_task(
                    "battycoda_app.audio.tasks.generate_recording_spectrogram", args=[recording.id]
                )
                request.session[f"recording_spectrogram_task_{recording_id}"] = task.id
                return JsonResponse({"success": True, "status": "processing"})
                
    except Exception as e:
        logger.error(f"Error checking spectrogram status: {str(e)}")
        return JsonResponse({"success": False, "status": "error", "error": str(e)})


@login_required
def upload_pickle_segments_view(request, recording_id):
    """Upload a pickle file to create segments for a recording"""
    recording = get_object_or_404(Recording, id=recording_id)
    
    # Check permission
    profile = request.user.profile
    if recording.created_by != request.user and (not profile.team or recording.team != profile.team):
        messages.error(request, "You don't have permission to add segments to this recording.")
        return redirect("battycoda_app:recording_detail", recording_id=recording.id)
    
    if request.method == "POST" and request.FILES.get("pickle_file"):
        pickle_file = request.FILES["pickle_file"]
        
        try:
            # Process the pickle file
            onsets, offsets = process_pickle_file(pickle_file)
            
            # Create segments from the onset/offset pairs
            segments_created = 0
            with transaction.atomic():
                for i in range(len(onsets)):
                    try:
                        # Create segment name
                        segment_name = f"Segment {i+1}"
                        
                        # Create and save the segment
                        segment = Segment(
                            recording=recording,
                            name=segment_name,
                            onset=onsets[i],
                            offset=offsets[i],
                            created_by=request.user
                        )
                        segment.save()
                        segments_created += 1
                    except Exception as e:
                        logger.error(f"Error creating segment {i}: {str(e)}")
                        logger.error(traceback.format_exc())
                        raise  # Re-raise to trigger transaction rollback
            
            # Return appropriate response based on request type
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({
                    "success": True,
                    "message": f"Successfully created {segments_created} segments.",
                    "redirect_url": reverse("battycoda_app:segment_recording", kwargs={"recording_id": recording.id})
                })
            
            messages.success(request, f"Successfully created {segments_created} segments from pickle file.")
            return redirect("battycoda_app:segment_recording", recording_id=recording.id)
            
        except Exception as e:
            logger.error(f"Error processing pickle file: {str(e)}")
            
            # Return appropriate error response
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": str(e)})
            
            messages.error(request, f"Error processing pickle file: {str(e)}")
            return redirect("battycoda_app:segment_recording", recording_id=recording.id)
    
    # GET request - render upload form
    context = {
        "recording": recording,
    }
    
    return render(request, "recordings/upload_pickle.html", context)


@login_required
def get_audio_waveform_data(request, recording_id):
    """Get waveform data for a recording in JSON format"""
    recording = get_object_or_404(Recording, id=recording_id)
    
    # Check permission
    profile = request.user.profile
    if recording.created_by != request.user and (not profile.team or recording.team != profile.team):
        return JsonResponse({"success": False, "error": "Permission denied"}, status=403)
    
    try:
        import numpy as np
        import soundfile as sf
        from scipy import signal
        
        # Load the audio file
        audio_data, sample_rate = sf.read(recording.wav_file.path)
        
        # For stereo, convert to mono by averaging channels
        if len(audio_data.shape) > 1 and audio_data.shape[1] > 1:
            audio_data = np.mean(audio_data, axis=1)
        
        # Resample to reduce data size (target ~1000-2000 points for visualization)
        target_points = 2000
        if len(audio_data) > target_points:
            # Resample using scipy for better quality
            resampled_data = signal.resample(audio_data, target_points)
        else:
            resampled_data = audio_data
            
        # Convert to list and normalize between -1 and 1
        max_val = np.max(np.abs(resampled_data))
        if max_val > 0:
            normalized_data = resampled_data / max_val
        else:
            normalized_data = resampled_data
            
        # Convert to list of floats
        waveform_data = normalized_data.tolist()
        
        return JsonResponse({
            "success": True,
            "waveform": waveform_data,
            "duration": recording.duration,
            "sample_rate": sample_rate
        })
        
    except Exception as e:
        logger.error(f"Error generating waveform data: {str(e)}")
        # Make sure we always return duration even on error
        return JsonResponse({
            "success": False, 
            "error": str(e),
            "duration": recording.duration or 0,  # Ensure duration is never null
            "waveform": []  # Empty waveform data
        })