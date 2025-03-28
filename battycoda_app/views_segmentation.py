"""
Views for segmentation of audio recordings.
"""
import logging
import os
import traceback
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .audio.utils import process_pickle_file
from .forms import SegmentForm, SegmentFormSetFactory
from .models import Recording, Segment, Segmentation, SegmentationAlgorithm, UserProfile

# Set up logging
logger = logging.getLogger("battycoda.views_segmentation")


@login_required
def segment_recording_view(request, recording_id):
    """Manual segmentation of a recording"""
    # Get user profile
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Check if user has a group
    if not profile.group:
        messages.error(request, "You must be assigned to a group to segment recordings")
        return redirect("battycoda_app:recording_list")
    
    # Get the recording (ensure it belongs to the user's group)
    recording = get_object_or_404(Recording, id=recording_id, group=profile.group)
    
    # Get active segmentation or create a new one for manual segmentation
    active_segmentation = Segmentation.objects.filter(
        recording=recording, is_active=True
    ).first()
    
    if not active_segmentation:
        # Create a new segmentation for manual segments
        active_segmentation = Segmentation.objects.create(
            recording=recording,
            name=f"Manual Segmentation {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}",
            algorithm=None,  # No algorithm for manual segmentation
            status='completed',
            progress=100,
            is_active=True,
            manually_edited=True,
            created_by=request.user
        )
    
    # Get all segments for the active segmentation
    segments = Segment.objects.filter(
        recording=recording, segmentation=active_segmentation
    ).order_by("onset")
    
    # Initialize the formset for segments
    SegmentFormSet = SegmentFormSetFactory(extra=0)
    
    if request.method == "POST":
        # Process the form submission
        formset = SegmentFormSet(request.POST, prefix="segments", queryset=segments)
        
        if formset.is_valid():
            # Mark the segmentation as manually edited
            active_segmentation.manually_edited = True
            active_segmentation.save()
            
            # Save the formset (will handle updates and deletes)
            instances = formset.save(commit=False)
            
            # Add the recording, segmentation, and user to each segment and save
            for instance in instances:
                instance.recording = recording
                instance.segmentation = active_segmentation
                instance.created_by = request.user
                instance.save(manual_edit=True)
            
            # Handle deleted forms
            for obj in formset.deleted_objects:
                obj.delete()
            
            # Check for new segment creation via AJAX
            if 'onset' in request.POST and 'offset' in request.POST:
                try:
                    onset = float(request.POST.get('onset'))
                    offset = float(request.POST.get('offset'))
                    
                    # Create a new segment and save it
                    new_segment = Segment(
                        recording=recording,
                        segmentation=active_segmentation,
                        name=f"Segment {segments.count() + 1}",
                        onset=onset,
                        offset=offset,
                        created_by=request.user
                    )
                    new_segment.save(manual_edit=True)
                    
                    # Return JSON response for AJAX requests
                    return JsonResponse({
                        'success': True,
                        'segment': {
                            'id': new_segment.id,
                            'name': new_segment.name,
                            'onset': new_segment.onset,
                            'offset': new_segment.offset
                        }
                    })
                except Exception as e:
                    logger.error(f"Error creating new segment: {str(e)}")
                    return JsonResponse({'success': False, 'error': str(e)})
            
            # Regular form submission
            messages.success(request, "Segments updated successfully.")
            return redirect("battycoda_app:segment_recording", recording_id=recording.id)
    else:
        # Initialize the formset with existing segments
        formset = SegmentFormSet(prefix="segments", queryset=segments)
    
    context = {
        "recording": recording,
        "active_segmentation": active_segmentation,
        "segments": segments,
        "formset": formset,
    }
    
    return render(request, "recordings/segment_recording.html", context)


@login_required
def add_segment_view(request, recording_id):
    """Add a new segment to a recording via AJAX"""
    # Get user profile
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Check if user has a group
    if not profile.group:
        return JsonResponse({
            'success': False,
            'error': "You must be assigned to a group to add segments"
        })
    
    # Get the recording (ensure it belongs to the user's group)
    recording = get_object_or_404(Recording, id=recording_id, group=profile.group)
    
    if request.method == "POST":
        try:
            # Get onset and offset from the request
            onset = float(request.POST.get('onset'))
            offset = float(request.POST.get('offset'))
            
            # Get active segmentation or create a new one for manual segments
            active_segmentation = Segmentation.objects.filter(
                recording=recording, is_active=True
            ).first()
            
            if not active_segmentation:
                # Create a new segmentation for manual segments
                active_segmentation = Segmentation.objects.create(
                    recording=recording,
                    name=f"Manual Segmentation {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    algorithm=None,  # No algorithm for manual segmentation
                    status='completed',
                    progress=100,
                    is_active=True,
                    manually_edited=True,
                    created_by=request.user
                )
            
            # Count existing segments for naming
            segment_count = Segment.objects.filter(
                recording=recording, segmentation=active_segmentation
            ).count()
            
            # Create a new segment
            new_segment = Segment(
                recording=recording,
                segmentation=active_segmentation,
                name=f"Segment {segment_count + 1}",
                onset=onset,
                offset=offset,
                created_by=request.user
            )
            new_segment.save(manual_edit=True)
            
            # Mark the segmentation as manually edited
            active_segmentation.manually_edited = True
            active_segmentation.save()
            
            # Return success response
            return JsonResponse({
                'success': True,
                'segment': {
                    'id': new_segment.id,
                    'name': new_segment.name,
                    'onset': new_segment.onset,
                    'offset': new_segment.offset
                }
            })
        except Exception as e:
            logger.error(f"Error creating segment: {str(e)}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def edit_segment_view(request, segment_id):
    """Edit a segment via AJAX"""
    # Get the segment
    segment = get_object_or_404(Segment, id=segment_id)
    
    # Check if user has permission
    profile = request.user.profile
    if not profile.group or segment.recording.group != profile.group:
        return JsonResponse({'success': False, 'error': 'Permission denied'})
    
    if request.method == "POST":
        try:
            # Get form data
            form = SegmentForm(request.POST, instance=segment)
            
            if form.is_valid():
                # Update segment
                segment = form.save(commit=False)
                segment.save(manual_edit=True)
                
                # Mark the segmentation as manually edited
                segmentation = segment.segmentation
                segmentation.manually_edited = True
                segmentation.save()
                
                # Return success response
                return JsonResponse({
                    'success': True,
                    'segment': {
                        'id': segment.id,
                        'name': segment.name,
                        'onset': segment.onset,
                        'offset': segment.offset
                    }
                })
            else:
                return JsonResponse({'success': False, 'error': 'Invalid form data'})
        except Exception as e:
            logger.error(f"Error updating segment: {str(e)}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def delete_segment_view(request, segment_id):
    """Delete a segment via AJAX"""
    # Get the segment
    segment = get_object_or_404(Segment, id=segment_id)
    
    # Check if user has permission
    profile = request.user.profile
    if not profile.group or segment.recording.group != profile.group:
        return JsonResponse({'success': False, 'error': 'Permission denied'})
    
    if request.method == "POST":
        try:
            segmentation = segment.segmentation
            segment.delete()
            
            # Mark the segmentation as manually edited
            segmentation.manually_edited = True
            segmentation.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            logger.error(f"Error deleting segment: {str(e)}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def upload_pickle_segments_view(request, recording_id):
    """Upload a pickle file to automatically segment a recording"""
    # Get user profile
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Check if user has a group
    if not profile.group:
        messages.error(request, "You must be assigned to a group to upload segmentations")
        return redirect("battycoda_app:recording_list")
    
    # Get the recording (ensure it belongs to the user's group)
    recording = get_object_or_404(Recording, id=recording_id, group=profile.group)
    
    if request.method == "POST":
        try:
            pickle_file = request.FILES.get("pickle_file")
            
            if not pickle_file:
                messages.error(request, "Please select a pickle file to upload")
                return redirect("battycoda_app:upload_pickle_segmentation", recording_id=recording.id)
            
            # Process the pickle file to get onsets and offsets
            onsets, offsets = process_pickle_file(pickle_file)
            
            with transaction.atomic():
                # Mark all existing segmentations as inactive first
                Segmentation.objects.filter(recording=recording, is_active=True).update(is_active=False)
                
                # Create a new segmentation for the pickle file
                segmentation = Segmentation.objects.create(
                    recording=recording,
                    name=f"Pickle Upload {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    algorithm=None,  # No algorithm for uploaded pickles
                    status='completed',
                    progress=100,
                    is_active=True,
                    manually_edited=False,
                    created_by=request.user
                )
                
                # Create segments from the onset/offset pairs
                segments_created = 0
                for i in range(len(onsets)):
                    try:
                        # Create segment name
                        segment_name = f"Segment {i+1}"
                        
                        # Create and save the segment
                        segment = Segment(
                            recording=recording,
                            segmentation=segmentation,
                            name=segment_name,
                            onset=onsets[i],
                            offset=offsets[i],
                            created_by=request.user
                        )
                        segment.save(manual_edit=False)  # Don't mark as manually edited for automated uploads
                        segments_created += 1
                    except Exception as e:
                        logger.error(f"Error creating segment {i}: {str(e)}")
                
                # Update segment count on the segmentation
                segmentation.segments_created = segments_created
                segmentation.save()
                
                if segments_created > 0:
                    messages.success(request, f"Successfully created {segments_created} segments from pickle file")
                else:
                    messages.warning(request, "No segments could be created from the pickle file")
        except Exception as e:
            logger.error(f"Error processing pickle file: {str(e)}")
            logger.error(traceback.format_exc())
            messages.error(request, f"Error processing pickle file: {str(e)}")
        
        return redirect("battycoda_app:recording_detail", recording_id=recording.id)
    
    context = {
        "recording": recording,
    }
    
    return render(request, "recordings/upload_pickle.html", context)


@login_required
def batch_segmentation_view(request):
    """Batch segmentation of recordings"""
    # Get user profile
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Check if user has a group
    if not profile.group:
        messages.error(request, "You must be assigned to a group to use batch segmentation")
        return redirect("battycoda_app:recording_list")
    
    # Get available segmentation algorithms
    algorithms = SegmentationAlgorithm.objects.all()
    
    # Get all recordings for the user's group
    recordings = Recording.objects.filter(group=profile.group)
    
    if request.method == "POST":
        # Get selected algorithm and recordings
        algorithm_id = request.POST.get("algorithm")
        recording_ids = request.POST.getlist("recordings")
        
        if not algorithm_id:
            messages.error(request, "Please select an algorithm")
            return redirect("battycoda_app:batch_segmentation")
        
        if not recording_ids:
            messages.error(request, "Please select at least one recording")
            return redirect("battycoda_app:batch_segmentation")
        
        # Create segmentation jobs for each selected recording
        algorithm = get_object_or_404(SegmentationAlgorithm, id=algorithm_id)
        
        for recording_id in recording_ids:
            recording = get_object_or_404(Recording, id=recording_id, group=profile.group)
            
            # Create a segmentation job
            segmentation = Segmentation.objects.create(
                recording=recording,
                name=f"{algorithm.name} {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}",
                algorithm=algorithm,
                status='pending',
                progress=0,
                is_active=False,  # Don't make active until completed
                manually_edited=False,
                created_by=request.user
            )
            
            # Queue the segmentation task
            from .tasks import process_segmentation
            process_segmentation.delay(segmentation.id)
        
        messages.success(request, f"Segmentation jobs created for {len(recording_ids)} recordings")
        return redirect("battycoda_app:segmentation_jobs_status")
    
    context = {
        "algorithms": algorithms,
        "recordings": recordings,
    }
    
    return render(request, "recordings/batch_segmentation.html", context)


@login_required
def segmentation_jobs_status_view(request):
    """View status of segmentation jobs"""
    # Get user profile
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Check if user has a group
    if not profile.group:
        messages.error(request, "You must be assigned to a group to view segmentation jobs")
        return redirect("battycoda_app:recording_list")
    
    # Get recent segmentation jobs for the user's group
    segmentations = Segmentation.objects.filter(
        recording__group=profile.group
    ).order_by("-created_at")[:50]  # Limit to recent 50
    
    context = {
        "segmentations": segmentations,
    }
    
    return render(request, "recordings/segmentation_jobs_status.html", context)


@login_required
def auto_segment_recording_view(request, recording_id, algorithm_id=None):
    """Automatically segment a recording using an algorithm"""
    # Get user profile
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Check if user has a group
    if not profile.group:
        messages.error(request, "You must be assigned to a group to segment recordings")
        return redirect("battycoda_app:recording_list")
    
    # Get the recording (ensure it belongs to the user's group)
    recording = get_object_or_404(Recording, id=recording_id, group=profile.group)
    
    # Get available segmentation algorithms
    algorithms = SegmentationAlgorithm.objects.all()
    
    if request.method == "POST" or algorithm_id:
        # Get selected algorithm
        selected_algorithm_id = algorithm_id or request.POST.get("algorithm")
        
        if not selected_algorithm_id:
            messages.error(request, "Please select an algorithm")
            return redirect("battycoda_app:auto_segment_recording", recording_id=recording.id)
        
        algorithm = get_object_or_404(SegmentationAlgorithm, id=selected_algorithm_id)
        
        # Create a segmentation job
        segmentation = Segmentation.objects.create(
            recording=recording,
            name=f"{algorithm.name} {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}",
            algorithm=algorithm,
            status='pending',
            progress=0,
            is_active=False,  # Don't make active until completed
            manually_edited=False,
            created_by=request.user
        )
        
        # Queue the segmentation task
        from .tasks import process_segmentation
        process_segmentation.delay(segmentation.id)
        
        messages.success(request, f"Segmentation job created with algorithm: {algorithm.name}")
        return redirect("battycoda_app:recording_detail", recording_id=recording.id)
    
    context = {
        "recording": recording,
        "algorithms": algorithms,
    }
    
    return render(request, "recordings/auto_segment.html", context)


@login_required
def auto_segment_status_view(request, recording_id):
    """Check the status of auto-segmentation for a recording via AJAX"""
    # Get user profile
    profile = request.user.profile
    
    # Check if user has permission
    if not profile.group:
        return JsonResponse({'success': False, 'error': 'Permission denied'})
    
    # Get the recording
    recording = get_object_or_404(Recording, id=recording_id, group=profile.group)
    
    # Get the latest segmentation jobs for this recording
    segmentations = Segmentation.objects.filter(
        recording=recording,
        algorithm__isnull=False  # Only include algorithm-based segmentations
    ).order_by("-created_at")[:5]  # Limit to most recent 5
    
    # Format response data
    segmentation_data = []
    for segmentation in segmentations:
        segmentation_data.append({
            'id': segmentation.id,
            'name': segmentation.name,
            'status': segmentation.status,
            'progress': segmentation.progress,
            'created_at': segmentation.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            'is_active': segmentation.is_active,
            'segments_created': segmentation.segments_created or 0
        })
    
    return JsonResponse({
        'success': True,
        'segmentations': segmentation_data
    })