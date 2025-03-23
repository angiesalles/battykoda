import logging
import pickle
import traceback
import numpy as np
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.http import JsonResponse
from django.db import transaction
from .models import UserProfile, Task, TaskBatch
from .forms import TaskBatchForm

# Set up logging
logger = logging.getLogger('battycoda.views_task_batch')

@login_required
def task_batch_list_view(request):
    """Display list of all task batches"""
    # Get user profile
    profile = request.user.profile
    
    # Filter batches by team if the user is in a team
    if profile.team:
        if profile.is_admin:
            # Admin sees all batches in their team
            batches = TaskBatch.objects.filter(team=profile.team).order_by('-created_at')
        else:
            # Regular user only sees their own batches
            batches = TaskBatch.objects.filter(created_by=request.user).order_by('-created_at')
    else:
        # Fallback to showing only user's batches if no team is assigned
        batches = TaskBatch.objects.filter(created_by=request.user).order_by('-created_at')
    
    context = {
        'batches': batches,
    }
    
    return render(request, 'tasks/batch_list.html', context)

@login_required
def task_batch_detail_view(request, batch_id):
    """Display details of a specific task batch"""
    # Get the batch by ID
    batch = get_object_or_404(TaskBatch, id=batch_id)
    
    # Check if the user has permission to view this batch
    # Either they created it or they're in the same team
    profile = request.user.profile
    if batch.created_by != request.user and (not profile.team or batch.team != profile.team):
        messages.error(request, "You don't have permission to view this batch.")
        return redirect('battycoda_app:task_batch_list')
    
    # Get tasks with ascending ID order
    tasks = Task.objects.filter(batch=batch).order_by('id')  # Ordering by ID in ascending order
    
    context = {
        'batch': batch,
        'tasks': tasks,
    }
    
    return render(request, 'tasks/batch_detail.html', context)

@login_required
def create_task_batch_view(request):
    """Handle creation of a new task batch with pickle file and wav file upload"""
    if request.method == 'POST':
        form = TaskBatchForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            # Create the task batch but don't save yet
            batch = form.save(commit=False)
            batch.created_by = request.user
            
            # Get user profile
            profile, created = UserProfile.objects.get_or_create(user=request.user)
            
            # Set team to user's current active team
            if profile.team:
                batch.team = profile.team
            else:
                # This is a critical issue - user must have a team
                messages.error(request, 'You must be assigned to a team to create a task batch')
                return redirect('battycoda_app:create_task_batch')
            
            # Get the WAV file from the form and set the wav_file_name from it
            if 'wav_file' in request.FILES:
                # The wav_file field will be saved automatically when the form is saved
                # Always set wav_file_name from the uploaded file's name
                wav_file = request.FILES['wav_file']
                batch.wav_file_name = wav_file.name
            else:
                messages.error(request, 'WAV file is required')
                return redirect('battycoda_app:create_task_batch')
            
            # Save the batch with files
            batch.save()
            
            # Process the pickle file
            pickle_file = request.FILES['pickle_file']
            
            try:
                # Load the pickle file
                pickle_data = pickle.load(pickle_file)
                
                # Extract onsets and offsets
                # Check if the data is a dictionary or a list
                if isinstance(pickle_data, dict):
                    onsets = pickle_data.get('onsets', [])
                    offsets = pickle_data.get('offsets', [])
                elif isinstance(pickle_data, list) and len(pickle_data) >= 2:
                    # Assume first item is onsets, second is offsets
                    onsets = pickle_data[0]
                    offsets = pickle_data[1]
                elif isinstance(pickle_data, tuple) and len(pickle_data) >= 2:
                    # Assume first item is onsets, second is offsets
                    onsets = pickle_data[0]
                    offsets = pickle_data[1]
                else:
                    # Unrecognized format
                    onsets = []
                    offsets = []
                    logger.error(f"Pickle file format not recognized: {type(pickle_data)}")
                
                # Convert to lists if they're NumPy arrays or other iterables
                if isinstance(onsets, np.ndarray):
                    onsets = onsets.tolist()
                elif not isinstance(onsets, list):
                    onsets = list(onsets)
                    
                if isinstance(offsets, np.ndarray):
                    offsets = offsets.tolist()
                elif not isinstance(offsets, list):
                    offsets = list(offsets)
                
                # Validate data
                if len(onsets) == 0 or len(offsets) == 0:
                    messages.error(request, 'Pickle file does not contain required onset and offset lists.')
                    return redirect('battycoda_app:create_task_batch')
                
                # Check if lists are the same length
                if len(onsets) != len(offsets):
                    messages.error(request, 'Onsets and offsets lists must have the same length.')
                    return redirect('battycoda_app:create_task_batch')
                
                # Create tasks for each onset-offset pair inside a transaction
                tasks_created = 0
                with transaction.atomic():
                    for i in range(len(onsets)):
                        try:
                            # Convert numpy types to Python native types if needed
                            onset_value = float(onsets[i])
                            offset_value = float(offsets[i])
                            
                            # Create and save the task
                            task = Task(
                                wav_file_name=batch.wav_file_name,
                                onset=onset_value,
                                offset=offset_value,
                                species=batch.species,
                                project=batch.project,
                                batch=batch,
                                created_by=request.user,
                                team=profile.team,
                                status='pending'
                            )
                            task.save()
                            tasks_created += 1
                        except Exception as e:
                            logger.error(f"Error creating task {i}: {str(e)}")
                            logger.error(traceback.format_exc())
                            raise  # Re-raise to trigger transaction rollback
                
                # Check if AJAX request
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': f'Successfully created batch with {tasks_created} tasks.',
                        'redirect_url': reverse('battycoda_app:task_batch_detail', kwargs={'batch_id': batch.id})
                    })
                
                messages.success(request, f'Successfully created batch with {tasks_created} tasks.')
                return redirect('battycoda_app:task_batch_detail', batch_id=batch.id)
                
            except Exception as e:
                logger.error(f"Error processing pickle file: {str(e)}")
                logger.error(traceback.format_exc())
                
                # Delete the batch if pickle processing failed
                if batch.id:
                    batch.delete()
                
                # Return JSON response for AJAX requests
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': f'Error processing file: {str(e)}'
                    })
                    
                messages.error(request, f'Error processing pickle file: {str(e)}')
                batch.delete()
                
                return redirect('battycoda_app:create_task_batch')
    else:
        form = TaskBatchForm(user=request.user)
    
    context = {
        'form': form,
    }
    
    return render(request, 'tasks/create_batch.html', context)