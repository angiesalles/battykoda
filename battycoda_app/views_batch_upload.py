"""
Views for handling batch uploads of recordings.
"""
import logging
import os
import tempfile
import traceback
import zipfile
import uuid
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .audio.utils import process_pickle_file
from .forms import RecordingForm
from .models import Recording, Segment, Segmentation, UserProfile

# Set up logging
logger = logging.getLogger("battycoda.views_batch_upload")

# Dictionary to store upload progress data
UPLOAD_PROGRESS = {}

class UploadProgressMiddleware:
    """Middleware to track upload progress"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Only track progress for the batch upload endpoint
        if request.method == 'POST' and request.path.endswith('/batch-upload/'):
            # Generate a unique ID for this upload
            upload_id = str(uuid.uuid4())
            request.upload_id = upload_id
            UPLOAD_PROGRESS[upload_id] = {
                'total': int(request.META.get('CONTENT_LENGTH', 0)),
                'uploaded': 0,
                'status': 'uploading',
                'timestamp': timezone.now()
            }
            
            # Get original read method
            original_read = request.META.get('wsgi.input').read
            
            # Define a tracking read method
            def tracking_read(*args, **kwargs):
                # Call the original read method
                data = original_read(*args, **kwargs)
                
                # Update the progress
                if upload_id in UPLOAD_PROGRESS:
                    UPLOAD_PROGRESS[upload_id]['uploaded'] += len(data)
                    
                return data
            
            # Replace the read method
            request.META.get('wsgi.input').read = tracking_read
        
        # Get response from next middleware or view
        response = self.get_response(request)
        
        # Clean up old progress entries (older than 1 hour)
        current_time = timezone.now()
        keys_to_delete = []
        for key, data in UPLOAD_PROGRESS.items():
            # Delete entries older than 1 hour
            if (current_time - data.get('timestamp')).total_seconds() > 3600:
                keys_to_delete.append(key)
        
        # Remove old entries
        for key in keys_to_delete:
            UPLOAD_PROGRESS.pop(key, None)
            
        return response

@csrf_exempt
def upload_progress_view(request):
    """View to get upload progress"""
    upload_id = request.GET.get('upload_id', '')
    
    if upload_id in UPLOAD_PROGRESS:
        progress_data = UPLOAD_PROGRESS[upload_id]
        total = progress_data['total']
        uploaded = progress_data['uploaded']
        status = progress_data['status']
        
        if total > 0:
            percent = int((uploaded / total) * 100)
        else:
            percent = 0
            
        return JsonResponse({
            'total': total,
            'uploaded': uploaded,
            'percent': percent,
            'status': status
        })
    
    return JsonResponse({
        'percent': 0,
        'status': 'unknown'
    })


@login_required
def batch_upload_recordings_view(request):
    """Handle batch upload of recordings with optional pickle segmentation files from ZIP archives"""
    
    # Get user profile
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Check if user has a group
    if not profile.group:
        messages.error(request, "You must be assigned to a group to upload recordings")
        return redirect("battycoda_app:recording_list")
    
    if request.method == "POST":
        # If upload_id was set by middleware, save it in the context
        if hasattr(request, 'upload_id'):
            # Set upload_id in session for client-side access
            request.session['upload_id'] = request.upload_id
        # Log the POST request
        logger.info("POST request received for batch upload")
        logger.info(f"POST data keys: {list(request.POST.keys())}")
        logger.info(f"FILES data keys: {list(request.FILES.keys())}")
        
        # Create a form instance with submitted data
        form = RecordingForm(request.POST, request.FILES, user=request.user)
        
        # Process form for common metadata
        if form.is_valid():
            logger.info("Form is valid, processing upload")
            
            # Get common fields from the form but don't save yet
            species = form.cleaned_data.get("species")
            project = form.cleaned_data.get("project")
            description = form.cleaned_data.get("description")
            recorded_date = form.cleaned_data.get("recorded_date")
            location = form.cleaned_data.get("location")
            equipment = form.cleaned_data.get("equipment")
            environmental_conditions = form.cleaned_data.get("environmental_conditions")
            
            # Get uploaded zip files
            wav_zip = request.FILES.get("wav_zip")
            pickle_zip = request.FILES.get("pickle_zip")
            
            # Debug logging
            logger.info(f"Form is valid. WAV zip present: {wav_zip is not None}, Pickle zip present: {pickle_zip is not None}")
            
            if not wav_zip:
                messages.error(request, "Please select a ZIP file with WAV recordings to upload")
                return redirect("battycoda_app:batch_upload_recordings")
            
            success_count = 0
            error_count = 0
            segmented_count = 0
            
            # Update status if upload_id is set
            if hasattr(request, 'upload_id') and request.upload_id in UPLOAD_PROGRESS:
                UPLOAD_PROGRESS[request.upload_id]['status'] = 'processing'
            
            # Create temporary directories for extracted files
            with tempfile.TemporaryDirectory() as wav_temp_dir, tempfile.TemporaryDirectory() as pickle_temp_dir:
                # Extract WAV files from zip
                wav_files = []
                try:
                    with zipfile.ZipFile(wav_zip, 'r') as zip_ref:
                        # Extract all wav files - filtering out directories and duplicate paths
                        processed_files = set()  # Track files to avoid duplicates
                        
                        # Debug: print contents of the ZIP
                        logger.info(f"ZIP file contains {len(zip_ref.namelist())} items:")
                        for filename in zip_ref.namelist():
                            logger.info(f"  - {filename} {'[DIR]' if filename.endswith('/') else ''}")
                        
                        for file_info in zip_ref.infolist():
                            # Skip directories, already processed files, and macOS metadata files
                            if (file_info.filename.endswith('/') or 
                                file_info.filename in processed_files or
                                os.path.basename(file_info.filename).startswith('._')):
                                logger.info(f"Skipping {file_info.filename} - directory, duplicate, or macOS metadata file")
                                continue
                                
                            if file_info.filename.lower().endswith('.wav'):
                                logger.info(f"Processing WAV file from ZIP: {file_info.filename}")
                                zip_ref.extract(file_info, wav_temp_dir)
                                extracted_path = os.path.join(wav_temp_dir, file_info.filename)
                                wav_files.append(extracted_path)
                                processed_files.add(file_info.filename)
                                logger.info(f"Extracted to: {extracted_path}")
                                
                    logger.info(f"Extracted {len(wav_files)} WAV files from ZIP")
                except Exception as e:
                    messages.error(request, f"Failed to extract WAV ZIP file: {str(e)}")
                    logger.error(f"ZIP extraction error: {str(e)}")
                    logger.error(traceback.format_exc())
                    return redirect("battycoda_app:batch_upload_recordings")
                
                # Extract pickle files if available
                pickle_files_dict = {}
                if pickle_zip:
                    try:
                        with zipfile.ZipFile(pickle_zip, 'r') as zip_ref:
                            # Extract all pickle files - filtering out directories and duplicate paths
                            processed_files = set()  # Track files to avoid duplicates
                            
                            for file_info in zip_ref.infolist():
                                # Skip directories, already processed files, and macOS metadata files
                                if (file_info.filename.endswith('/') or 
                                    file_info.filename in processed_files or 
                                    os.path.basename(file_info.filename).startswith('._')):
                                    continue
                                    
                                if file_info.filename.lower().endswith('.pickle'):
                                    zip_ref.extract(file_info, pickle_temp_dir)
                                    pickle_path = os.path.join(pickle_temp_dir, file_info.filename)
                                    # Store with basename as key for matching
                                    pickle_files_dict[os.path.basename(file_info.filename)] = pickle_path
                                    processed_files.add(file_info.filename)
                                    
                        logger.info(f"Extracted {len(pickle_files_dict)} pickle files from ZIP")
                    except Exception as e:
                        messages.error(request, f"Failed to extract pickle ZIP file: {str(e)}")
                        logger.error(f"Pickle ZIP extraction error: {str(e)}")
                        logger.error(traceback.format_exc())
                        # Continue with WAV files even if pickle extraction fails
                
                # Process each WAV file
                for wav_path in wav_files:
                    try:
                        logger.info(f"Processing WAV file: {wav_path}")
                        # Open the file for Django to save
                        with open(wav_path, 'rb') as wav_file_obj:
                            # Create a Django file object
                            wav_file_name = os.path.basename(wav_path)
                            wav_file = SimpleUploadedFile(wav_file_name, wav_file_obj.read(), content_type="audio/wav")
                            
                            with transaction.atomic():
                                # Create a Recording object for this file
                                file_name = Path(wav_file_name).stem  # Get file name without extension
                                
                                # Use the file name directly as the recording name
                                recording_name = file_name
                                
                                # Create the recording model instance
                                recording = Recording(
                                    name=recording_name,  # Use file name as recording name
                                    description=description,
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
                                logger.info(f"Created recording: {recording.name} (ID: {recording.id})")
                                
                                # Check if there's a matching pickle file
                                pickle_filename = f"{wav_file_name}.pickle"
                                pickle_path = pickle_files_dict.get(pickle_filename)
                                
                                # Process pickle file if found
                                if pickle_path:
                                    try:
                                        logger.info(f"Found matching pickle file: {pickle_filename}")
                                        # Open and process the pickle file
                                        with open(pickle_path, 'rb') as pickle_file_obj:
                                            # Create a Django file object
                                            pickle_file = SimpleUploadedFile(
                                                pickle_filename, 
                                                pickle_file_obj.read(),
                                                content_type="application/octet-stream"
                                            )
                                            
                                            # Process the pickle file
                                            onsets, offsets = process_pickle_file(pickle_file)
                                            logger.info(f"Processed pickle file. Found {len(onsets)} segments")
                                            
                                            # Mark all existing segmentations as inactive first
                                            Segmentation.objects.filter(recording=recording, is_active=True).update(is_active=False)
                                            
                                            # Create a new segmentation for this batch of segments
                                            segmentation = Segmentation.objects.create(
                                                recording=recording,
                                                name=f"Batch Upload {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}",
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
                                                    
                                                    # Create and save the segment - linked to the new segmentation
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
                                                    logger.error(f"Error creating segment {i} for {recording.name}: {str(e)}")
                                                    logger.error(traceback.format_exc())
                                            
                                            # Update segment count on the segmentation
                                            segmentation.segments_created = segments_created
                                            segmentation.save()
                                            
                                            if segments_created > 0:
                                                segmented_count += 1
                                                logger.info(f"Created {segments_created} segments for recording {recording.name}")
                                    except Exception as e:
                                        logger.error(f"Error processing pickle file for {recording.name}: {str(e)}")
                                        logger.error(traceback.format_exc())
                                
                                success_count += 1
                    except Exception as e:
                        logger.error(f"Error creating recording from {wav_path}: {str(e)}")
                        logger.error(traceback.format_exc())
                        error_count += 1
            
            # Update upload status if we have an upload_id
            if hasattr(request, 'upload_id') and request.upload_id in UPLOAD_PROGRESS:
                # Mark as complete
                UPLOAD_PROGRESS[request.upload_id]['status'] = 'complete'
                
            # Success message
            if success_count > 0:
                success_msg = f"Successfully uploaded {success_count} recordings"
                if segmented_count > 0:
                    success_msg += f" with {segmented_count} segmented automatically from pickle files"
                messages.success(request, success_msg)
                logger.info(success_msg)
            
            # Error message
            if error_count > 0:
                error_msg = f"Failed to upload {error_count} recordings. See logs for details."
                messages.error(request, error_msg)
                logger.error(error_msg)
            
            # Redirect to the recordings list
            return redirect("battycoda_app:recording_list")
        else:
            logger.error(f"Form validation errors: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Error in {field}: {error}")
    else:
        # GET request - display the form
        form = RecordingForm(user=request.user)
    
    context = {
        "form": form,
    }
    
    return render(request, "recordings/batch_upload_recordings.html", context)