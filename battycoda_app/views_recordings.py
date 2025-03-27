import hashlib
import logging
import mimetypes
import os
import re
import traceback
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse, JsonResponse, StreamingHttpResponse

# Removed unused import: http_date
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

# Removed unused import: generate_recording_spectrogram
from .audio.utils import process_pickle_file
from .forms import RecordingForm, SegmentForm, SegmentFormSetFactory
from .models import Recording, Segment, UserProfile

# Set up logging
logger = logging.getLogger("battycoda.views_recordings")

# Default chunk size for streaming (1MB)
CHUNK_SIZE = 1024 * 1024


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
        "page_description": "Apply segmentation strategies to multiple recordings at once."
    }

    return render(request, "recordings/batch_segmentation.html", context)


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
    if recording.created_by != request.user and (not profile.group or recording.group != profile.group or not profile.is_admin):
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
    if recording.created_by != request.user and (not profile.group or recording.group != profile.group or not profile.is_admin):
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
    if recording.created_by != request.user and (not profile.group or recording.group != profile.group):
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
    if recording.created_by != request.user and (not profile.group or recording.group != profile.group):
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
    if segment.created_by != request.user and (not profile.group or recording.group != profile.group):
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
    if segment.created_by != request.user and (not profile.group or recording.group != profile.group):
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
    if recording.created_by != request.user and (not profile.group or recording.group != profile.group):
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
def batch_upload_recordings_view(request):
    """Handle batch upload of multiple recordings with optional pickle segmentation files"""
    
    # Get user profile
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Check if user has a group
    if not profile.group:
        messages.error(request, "You must be assigned to a group to upload recordings")
        return redirect("battycoda_app:recording_list")
    
    if request.method == "POST":
        form = RecordingForm(request.POST, request.FILES, user=request.user)
        
        # Process form for common metadata
        if form.is_valid():
            # Get common fields from the form but don't save yet
            species = form.cleaned_data.get("species")
            project = form.cleaned_data.get("project")
            recorded_date = form.cleaned_data.get("recorded_date")
            location = form.cleaned_data.get("location")
            equipment = form.cleaned_data.get("equipment")
            environmental_conditions = form.cleaned_data.get("environmental_conditions")
            
            # Get uploaded wav files
            wav_files = request.FILES.getlist("wav_files")
            
            if not wav_files:
                messages.error(request, "Please select at least one WAV file to upload")
                return redirect("battycoda_app:batch_upload_recordings")
            
            success_count = 0
            error_count = 0
            segmented_count = 0
            
            # Process each WAV file
            for wav_file in wav_files:
                try:
                    with transaction.atomic():
                        # Create a Recording object for this file
                        file_name = Path(wav_file.name).stem  # Get file name without extension
                        recording = Recording(
                            name=file_name,  # Use file name as recording name
                            description=form.cleaned_data.get("description"),
                            wav_file=wav_file,
                            recorded_date=recorded_date,
                            location=location,
                            equipment=equipment,
                            environmental_conditions=environmental_conditions,
                            species=species,
                            project=project,
                            group=profile.group,
                            created_by=request.user
                        )
                        
                        # Save the recording
                        recording.save()
                        
                        # Check if there's a matching pickle file in the uploaded files
                        pickle_filename = f"{wav_file.name}.pickle"
                        pickle_file = None
                        
                        for uploaded_file in request.FILES.getlist("pickle_files"):
                            if uploaded_file.name == pickle_filename:
                                pickle_file = uploaded_file
                                break
                        
                        # Process pickle file if found
                        if pickle_file:
                            try:
                                # Process the pickle file
                                onsets, offsets = process_pickle_file(pickle_file)
                                
                                # Create segments from the onset/offset pairs
                                segments_created = 0
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
                                        logger.error(f"Error creating segment {i} for {recording.name}: {str(e)}")
                                
                                if segments_created > 0:
                                    segmented_count += 1
                                    logger.info(f"Created {segments_created} segments for recording {recording.name}")
                            except Exception as e:
                                logger.error(f"Error processing pickle file for {recording.name}: {str(e)}")
                                logger.error(traceback.format_exc())
                        
                        success_count += 1
                except Exception as e:
                    logger.error(f"Error creating recording from {wav_file.name}: {str(e)}")
                    logger.error(traceback.format_exc())
                    error_count += 1
            
            # Success message
            if success_count > 0:
                success_msg = f"Successfully uploaded {success_count} recordings"
                if segmented_count > 0:
                    success_msg += f" with {segmented_count} segmented automatically from pickle files"
                messages.success(request, success_msg)
            
            # Error message
            if error_count > 0:
                messages.error(request, f"Failed to upload {error_count} recordings. See logs for details.")
            
            # Redirect to the recordings list
            return redirect("battycoda_app:recording_list")
    else:
        # GET request - display the form
        form = RecordingForm(user=request.user)
    
    context = {
        "form": form,
    }
    
    return render(request, "recordings/batch_upload_recordings.html", context)


@login_required
def get_audio_waveform_data(request, recording_id):
    """Get waveform data for a recording in JSON format"""
    recording = get_object_or_404(Recording, id=recording_id)
    
    # Check permission
    profile = request.user.profile
    if recording.created_by != request.user and (not profile.group or recording.group != profile.group):
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


@login_required
def auto_segment_recording_view(request, recording_id, algorithm_id=None):
    """Run automated segmentation on a recording"""
    recording = get_object_or_404(Recording, id=recording_id)
    
    # Check permission
    profile = request.user.profile
    if recording.created_by != request.user and (not profile.group or recording.group != profile.group):
        messages.error(request, "You don't have permission to segment this recording.")
        return redirect("battycoda_app:recording_detail", recording_id=recording_id)
    
    from .models import SegmentationAlgorithm, Segmentation

    # Get available algorithms
    if profile.group and profile.is_admin:
        # Admin sees all algorithms plus group-specific ones
        # First get all global algorithms
        global_query = SegmentationAlgorithm.objects.filter(
            is_active=True,
            group__isnull=True
        )
        
        # Then get group-specific algorithms
        group_query = SegmentationAlgorithm.objects.filter(
            is_active=True, 
            group=profile.group
        )
        
        # Get all the IDs of both queries
        global_ids = set(global_query.values_list('id', flat=True))
        group_ids = set(group_query.values_list('id', flat=True))
        
        # Combine the IDs without duplicates
        all_ids = global_ids.union(group_ids)
        
        # Now get all algorithms with these IDs in a single query
        algorithms = SegmentationAlgorithm.objects.filter(
            id__in=all_ids
        ).order_by('name')
    else:
        # Regular user sees only global algorithms
        algorithms = SegmentationAlgorithm.objects.filter(
            is_active=True,
            group__isnull=True
        ).order_by('name')
    
    # Get the selected algorithm
    if algorithm_id:
        algorithm = get_object_or_404(SegmentationAlgorithm, id=algorithm_id, is_active=True)
    else:
        # Use the first available algorithm (usually Standard Threshold)
        algorithm = algorithms.first()
    
    if request.method == "POST":
        # Get parameters from request
        algorithm_id = request.POST.get("algorithm", algorithm.id if algorithm else None)
        min_duration_ms = request.POST.get("min_duration_ms", 10)
        smooth_window = request.POST.get("smooth_window", 3)
        threshold_factor = request.POST.get("threshold_factor", 0.5)
        
        # Get the algorithm
        if algorithm_id:
            algorithm = get_object_or_404(SegmentationAlgorithm, id=algorithm_id, is_active=True)
            
            # Check if user has access to this algorithm
            if algorithm.group and (not profile.group or algorithm.group != profile.group):
                messages.error(request, "You don't have permission to use this algorithm.")
                return redirect("battycoda_app:auto_segment_recording", recording_id=recording_id)
        else:
            # No algorithm selected, use default
            algorithm = algorithms.first()
            
            if not algorithm:
                messages.error(request, "No segmentation algorithms available.")
                return redirect("battycoda_app:segment_recording", recording_id=recording_id)
        
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

            # Launch Celery task
            task = current_app.send_task(
                algorithm.celery_task,
                args=[recording.id, min_duration_ms, smooth_window, threshold_factor]
            )
            
            # Store task ID in session for status checking
            request.session[f"auto_segment_task_{recording_id}"] = task.id
            
            # Create or update a Segmentation entry to track this job
            segmentation, created = Segmentation.objects.get_or_create(
                recording=recording,
                defaults={
                    'created_by': request.user
                }
            )
            
            # Update the segmentation
            segmentation.algorithm = algorithm
            segmentation.task_id = task.id
            segmentation.status = 'in_progress'
            segmentation.progress = 0
            segmentation.save()
            
            # Set success message
            messages.success(request, f"Automated segmentation started using {algorithm.name}. This may take a few moments to complete.")
            
            # Handle AJAX requests
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({
                    "success": True, 
                    "message": f"Automated segmentation task started using {algorithm.name}",
                    "task_id": task.id,
                    "segmentation_id": segmentation.id
                })
                
            # Redirect to segment view
            return redirect("battycoda_app:segment_recording", recording_id=recording_id)
            
        except Exception as e:
            logger.error(f"Error starting auto segmentation task: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Set error message
            messages.error(request, f"Error starting segmentation: {str(e)}")
            
            # Handle AJAX requests
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": str(e)})
                
            # Redirect to segment view
            return redirect("battycoda_app:segment_recording", recording_id=recording_id)
    
    # GET request - display form for configuring segmentation or return JSON if AJAX
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        # Return JSON with algorithm details for AJAX requests
        if algorithm:
            return JsonResponse({
                "success": True,
                "algorithm_id": algorithm.id,
                "algorithm_name": algorithm.name,
                "algorithm_description": algorithm.description,
                "algorithm_type": algorithm.get_algorithm_type_display(),
                "min_duration_ms": algorithm.default_min_duration_ms,
                "smooth_window": algorithm.default_smooth_window,
                "threshold_factor": algorithm.default_threshold_factor
            })
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
        from .models import Segmentation
        segmentation = Segmentation.objects.filter(recording_id=recording_id).first()
        
        if segmentation and segmentation.task_id:
            task_id = segmentation.task_id
        else:
            return JsonResponse({"success": False, "status": "not_found", "message": "No active segmentation task found"})
    
    try:
        from celery.result import AsyncResult

        from .models import Segmentation

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
                        segmentation.status = 'completed'
                        segmentation.progress = 100
                        segmentation.save()
                    
                    # Clear task ID from session
                    if f"auto_segment_task_{recording_id}" in request.session:
                        del request.session[f"auto_segment_task_{recording_id}"]
                    
                    return JsonResponse({
                        "success": True,
                        "status": "completed",
                        "message": message,
                        "segments_created": segments_created,
                        "result": task_result
                    })
                else:
                    # Task returned error status
                    error_message = task_result.get("message", "Unknown error in segmentation task")
                    
                    # Update segmentation status
                    if segmentation:
                        segmentation.status = 'failed'
                        segmentation.save()
                    
                    # Clear task ID from session
                    if f"auto_segment_task_{recording_id}" in request.session:
                        del request.session[f"auto_segment_task_{recording_id}"]
                    
                    return JsonResponse({
                        "success": False,
                        "status": "failed",
                        "message": error_message
                    })
            else:
                # Task failed with exception
                error_info = str(result.result)
                
                # Update segmentation status
                if segmentation:
                    segmentation.status = 'failed'
                    segmentation.save()
                
                # Clear task ID from session
                if f"auto_segment_task_{recording_id}" in request.session:
                    del request.session[f"auto_segment_task_{recording_id}"]
                
                return JsonResponse({
                    "success": False,
                    "status": "failed",
                    "message": f"Segmentation task failed: {error_info}"
                })
        else:
            # Task is still running
            # Update segmentation status if it exists
            if segmentation and segmentation.status != 'in_progress':
                segmentation.status = 'in_progress'
                segmentation.save()
                
            return JsonResponse({
                "success": True,
                "status": "in_progress",
                "message": "Segmentation is still processing..."
            })
    
    except Exception as e:
        logger.error(f"Error checking segmentation task status: {str(e)}")
        logger.error(traceback.format_exc())
        
        return JsonResponse({
            "success": False,
            "status": "error",
            "message": f"Error checking task status: {str(e)}"
        })


@login_required
def stream_audio_view(request, recording_id):
    """
    Stream an audio file with support for HTTP Range requests.
    This allows seeking in the audio player without downloading the entire file.
    """
    recording = get_object_or_404(Recording, id=recording_id)
    
    # Check if the user has permission to access this recording
    profile = request.user.profile
    if recording.created_by != request.user and (not profile.group or recording.group != profile.group):
        raise Http404("You don't have permission to access this recording")
    
    # Get the file path and validate it exists
    file_path = recording.wav_file.path
    if not os.path.exists(file_path):
        logger.error(f"Audio file not found: {file_path}")
        raise Http404("Audio file not found")
    
    # Get file info
    file_size = os.path.getsize(file_path)
    content_type = mimetypes.guess_type(file_path)[0] or 'audio/wav'
    
    # Parse Range header if present
    range_header = request.META.get('HTTP_RANGE', '').strip()
    range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
    
    # Initialize start_byte and end_byte
    start_byte = 0
    end_byte = file_size - 1
    
    # Handle range request
    if range_match:
        start_byte = int(range_match.group(1))
        end_group = range_match.group(2)
        
        if end_group:
            end_byte = min(int(end_group), file_size - 1)
            
        # Calculate bytes to read
        bytes_to_read = end_byte - start_byte + 1
        
        # Create partial response
        response = StreamingHttpResponse(
            streaming_file_iterator(file_path, start_byte, end_byte),
            status=206,
            content_type=content_type
        )
        
        # Add Content-Range header
        response['Content-Range'] = f'bytes {start_byte}-{end_byte}/{file_size}'
        response['Content-Length'] = str(bytes_to_read)
    else:
        # If no range is requested, serve the entire file
        response = StreamingHttpResponse(
            streaming_file_iterator(file_path, 0, file_size - 1),
            content_type=content_type
        )
        response['Content-Length'] = str(file_size)
    
    # Add common headers
    response['Accept-Ranges'] = 'bytes'
    response['Content-Disposition'] = f'inline; filename="{os.path.basename(file_path)}"'
    
    # Return the response
    return response


def streaming_file_iterator(file_path, start_byte, end_byte):
    """Iterator function to stream a file in chunks, respecting byte range requests"""
    # Calculate bytes to read
    bytes_to_read = end_byte - start_byte + 1
    chunk_size = min(CHUNK_SIZE, bytes_to_read)
    
    # Open the file and seek to the start position
    with open(file_path, 'rb') as f:
        f.seek(start_byte)
        
        # Stream the file in chunks
        remaining = bytes_to_read
        while remaining > 0:
            chunk_size = min(chunk_size, remaining)
            data = f.read(chunk_size)
            if not data:
                break
            yield data
            remaining -= len(data)


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
        "page_description": "Apply segmentation strategies to multiple recordings and monitor segmentation jobs."
    }
    
    return render(request, "recordings/batch_segmentation.html", context)


@login_required
def segmentation_jobs_status_view(request):
    """API endpoint to get the status of all segmentation jobs for the user"""
    # Get user profile
    profile = request.user.profile
    
    # Import the Segmentation model
    from .models import Segmentation

    # Filter segmentations by user and group permissions
    if profile.group and profile.is_admin:
        # Admin sees all segmentations in their group
        segmentations = Segmentation.objects.filter(recording__group=profile.group).order_by("-created_at")
    else:
        # Regular user only sees their own segmentations
        segmentations = Segmentation.objects.filter(created_by=request.user).order_by("-created_at")
    
    # Check if any segmentations have pending task status that we should update
    if segmentations.filter(status__in=['pending', 'in_progress']).exists():
        from celery.result import AsyncResult
        
        for segmentation in segmentations.filter(status__in=['pending', 'in_progress']):
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
                            segmentation.status = 'completed'
                            segmentation.progress = 100
                            segmentation.save()
                        else:
                            # Task returned error status
                            error_message = task_result.get("message", "Unknown error in segmentation task")
                            segmentation.status = 'failed'
                            segmentation.save()
                    else:
                        # Task failed with exception
                        error_info = str(result.result)
                        segmentation.status = 'failed'
                        segmentation.save()
            except Exception as e:
                logger.error(f"Error updating segmentation status for segmentation {segmentation.id}: {str(e)}")
                # Don't update the status in case of error
    
    # Format the segmentations for the response
    formatted_jobs = []
    for segmentation in segmentations[:20]:  # Limit to 20 most recent segmentations
        # Count segments
        segments_count = segmentation.recording.segments.count()
        
        formatted_job = {
            'id': segmentation.id,
            'recording_id': segmentation.recording.id,
            'recording_name': segmentation.recording.name,
            'status': segmentation.status,
            'progress': segmentation.progress,
            'start_time': segmentation.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'segments_created': segments_count,
            'algorithm_name': segmentation.algorithm.name if segmentation.algorithm else "Manual Import",
            'algorithm_type': segmentation.algorithm.get_algorithm_type_display() if segmentation.algorithm else "Manual",
            'view_url': reverse('battycoda_app:segment_recording', kwargs={'recording_id': segmentation.recording.id}),
            'retry_url': reverse('battycoda_app:auto_segment_recording', kwargs={'recording_id': segmentation.recording.id}),
            'is_processing': segmentation.is_processing,
        }
        formatted_jobs.append(formatted_job)
    
    return JsonResponse({'success': True, 'jobs': formatted_jobs})