import logging
import os
import pickle
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone
from django.http import JsonResponse, HttpResponse, FileResponse
from django.db import transaction

from .forms import (
    UserRegisterForm, UserLoginForm, UserProfileForm, 
    TaskBatchForm, TaskForm, TaskUpdateForm,
    SpeciesForm, ProjectForm, CallForm, CallFormSetFactory,
    TeamForm
)
from .models import UserProfile, Task, TaskBatch, Species, Project, Call, Team

# Set up logging
logger = logging.getLogger('battycoda.views')

# Basic views
def index(request):
    """Main entry point that shows the welcome page"""
    if not request.user.is_authenticated:
        return redirect('battycoda_app:login')
    
    # Generate species links for the welcome page
    species_links = ""
    user_species = Species.objects.all()
    for species in user_species:
        species_links += f"<li><a href=\"/species/{species.id}/\">{species.name}</a></li>"
    
    context = {
        'species_links': species_links
    }
    
    return render(request, 'welcometoBC.html', context)

# Authentication views
def login_view(request):
    """Handle user login"""
    if request.user.is_authenticated:
        return redirect('battycoda_app:home')
        
    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            remember = form.cleaned_data.get('remember', False)
            
            user = authenticate(username=username, password=password)
            if user:
                login(request, user)
                
                # Update last login
                user.last_login = timezone.now()
                user.save()
                
                # Check for next parameter
                next_page = request.GET.get('next')
                if not next_page or not next_page.startswith('/'):
                    next_page = reverse('battycoda_app:home')
                
                return redirect(next_page)
        else:
            messages.error(request, 'Please check your login details and try again.')
    else:
        form = UserLoginForm()
        
    return render(request, 'auth/login.html', {'form': form})

def register_view(request):
    """Handle user registration"""
    if request.user.is_authenticated:
        return redirect('battycoda_app:home')
        
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Create user's home directory from template
            from .utils import ensure_user_directory_exists
            ensure_user_directory_exists(user.username)
            logger.info(f"Created home directory for new user {user.username}")
            
            # Send welcome email
            # TODO: Implement email sending
            
            messages.success(request, 'Registration successful! Please log in.')
            return redirect('battycoda_app:login')
    else:
        form = UserRegisterForm()
        
    return render(request, 'auth/register.html', {'form': form})

@login_required
def logout_view(request):
    """Handle user logout"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('battycoda_app:login')

@login_required
def profile_view(request):
    """Display user profile"""
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    context = {
        'user': request.user,
        'profile': profile,
    }
    
    return render(request, 'auth/profile.html', context)

@login_required
def edit_profile_view(request):
    """Edit user profile settings"""
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile, user=request.user)
        if form.is_valid():
            form.save()
            
            # Update user email if provided
            email = request.POST.get('email')
            if email and email != request.user.email:
                request.user.email = email
                request.user.save()
                
            messages.success(request, 'Profile updated successfully!')
            return redirect('battycoda_app:profile')
    else:
        form = UserProfileForm(instance=profile, user=request.user)
        
    context = {
        'form': form,
        'user': request.user,
        'profile': profile,
    }
    
    return render(request, 'auth/edit_profile.html', context)

def password_reset_request(request):
    """Handle password reset request"""
    if request.method == 'POST':
        email = request.POST.get('email')
        
        # Verify email exists
        user = User.objects.filter(email=email).first()
        if not user:
            messages.error(request, 'No account found with that email.')
            return render(request, 'auth/forgot_password.html')
            
        # TODO: Generate token and send reset email
        
        messages.success(request, 'Password reset instructions have been sent to your email.')
        return redirect('battycoda_app:login')
        
    return render(request, 'auth/forgot_password.html')

def password_reset(request, token):
    """Reset password with token"""
    # TODO: Verify token
    
    if request.method == 'POST':
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'auth/reset_password.html', {'token': token})
            
        # TODO: Update user password
        
        messages.success(request, 'Password has been reset successfully. Please log in.')
        return redirect('battycoda_app:login')
        
    return render(request, 'auth/reset_password.html', {'token': token})

def request_login_code(request):
    """Request one-time login code"""
    if request.method == 'POST':
        username = request.POST.get('username')
        
        user = User.objects.filter(username=username).first()
        if not user:
            messages.error(request, 'No account found with that username.')
            return render(request, 'auth/request_login_code.html')
            
        # TODO: Generate and send login code
        
        messages.success(request, 'Login code has been sent to your email.')
        return redirect('battycoda_app:login')
        
    return render(request, 'auth/request_login_code.html')

# Directory and navigation views
@login_required
def home_view(request):
    """Home page showing user directories and templates"""
    from .directory_handlers import list_users_directory
    return list_users_directory(request)

@login_required
def user_directory_view(request, username):
    """List the species directories for a user"""
    from .directory_handlers import list_species_directory
    from .utils import ensure_user_directory_exists
    
    # If the directory doesn't exist, create it from template (only for the current user)
    if request.user.username == username:
        user_dir_path = os.path.join('/home', username)
        if not os.path.exists(user_dir_path):
            logger.info(f"Auto-creating directory for user {username}")
            ensure_user_directory_exists(username)
    
    return list_species_directory(request, f"home/{username}", username)

@login_required
def species_directory_view(request, username, species):
    """List the contents of a species directory"""
    from .directory_handlers import list_project_directory
    return list_project_directory(request, f"home/{username}/{species}", username, species)

@login_required
def subdirectory_view(request, username, species, subpath):
    """List the contents of a subdirectory within a species directory"""
    from .directory_handlers import list_project_directory
    path = f"home/{username}/{species}/{subpath}"
    return list_project_directory(request, path, username, species)

@login_required
def species_info_view(request, species_name):
    """Display information about bat species templates"""
    # TODO: Implement the species info view
    context = {
        'species_name': species_name,
        'listicle': f'<h2>Species: {species_name}</h2><p>Information about this species template.</p>'
    }
    
    return render(request, 'listBC.html', context)

from django.views.decorators.csrf import csrf_exempt

@login_required
@csrf_exempt  # Properly exempt this view from CSRF protection
@require_http_methods(["GET", "POST"])
def create_directory_view(request):
    """Create a new directory in user's space"""
    
    if request.method == 'POST':
        path = request.POST.get('path')
        directory_name = request.POST.get('directory_name')
        
        if not path or not directory_name:
            messages.error(request, 'Path and directory name are required.')
            return redirect('battycoda_app:home')
            
        try:
            # Validate directory name (prevent path traversal)
            if '/' in directory_name or '\\' in directory_name or '..' in directory_name:
                messages.error(request, 'Invalid directory name.')
                return redirect(f'/{path}/')
                
            # Create the directory
            from .utils import convert_path_to_os_specific
            import os
            
            # Convert path to OS specific
            full_path = convert_path_to_os_specific(f"{path}/{directory_name}")
            
            # Check if directory already exists
            if os.path.exists(full_path):
                messages.error(request, f'Directory {directory_name} already exists.')
                return redirect(f'/{path}/')
                
            # Create the directory
            os.makedirs(full_path, exist_ok=True)
            
            # Set directory permissions to be writable
            try:
                import subprocess
                subprocess.run(['chmod', '-R', '777', full_path])
                logger.info(f"Set permissions for {full_path}")
            except Exception as e:
                logger.warning(f"Could not set permissions for {full_path}: {str(e)}")
            
            messages.success(request, f'Directory {directory_name} created successfully.')
            
        except Exception as e:
            logger.error(f"Error creating directory: {str(e)}")
            messages.error(request, f'Error creating directory: {str(e)}')
            
        # Check if AJAX request
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': f'Directory {directory_name} created successfully.'})
            
        return redirect(f'/{path}/')
        
    return redirect('battycoda_app:home')

@login_required
@csrf_exempt  # Properly exempt this view from CSRF protection
@require_http_methods(["GET", "POST"])
def upload_file_view(request):
    """Handle file uploads"""
    if request.method == 'POST':
        path = request.POST.get('path')
        file = request.FILES.get('file')
        
        if not file:
            messages.error(request, 'No file selected.')
            return redirect(f'/{path}/')
            
        try:
            # Validate filename (prevent path traversal)
            filename = file.name
            if '/' in filename or '\\' in filename or '..' in filename:
                messages.error(request, 'Invalid filename.')
                return redirect(f'/{path}/')
                
            # Save the file
            from .utils import convert_path_to_os_specific
            import os
            
            # Convert path to OS specific
            full_path = convert_path_to_os_specific(f"{path}/{filename}")
            
            # Check if file already exists
            if os.path.exists(full_path):
                messages.error(request, f'File {filename} already exists.')
                return redirect(f'/{path}/')
                
            # Save the file
            with open(full_path, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)
                    
            messages.success(request, f'File {filename} uploaded successfully.')
            
        except Exception as e:
            logger.error(f"Error uploading file: {str(e)}")
            error_message = f'Error uploading file: {str(e)}'
            messages.error(request, error_message)
            
            # If this is an AJAX request, return error in JSON
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': error_message
                }, status=500)
            
        # Check if AJAX request
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'File {filename} uploaded successfully.',
                'file_name': filename,
                'path': path
            })
            
        return redirect(f'/{path}/')
        
    return redirect('battycoda_app:home')

@login_required
def get_next_task_view(request):
    """Get the next undone task and redirect to the annotation interface"""
    # Look for a task that isn't done yet
    task = Task.objects.filter(
        created_by=request.user,
        is_done=False
    ).order_by('created_at').first()
    
    if task:
        # Redirect to the annotation interface with the task ID
        return redirect('battycoda_app:annotate_task', task_id=task.id)
    else:
        # No undone tasks found
        messages.info(request, 'No undone tasks found. Please create new tasks or task batches.')
        return redirect('battycoda_app:task_list')

@login_required
def get_last_task_view(request):
    """Get the last task the user worked on (most recently updated) and redirect to it"""
    # Get the most recently updated task
    task = Task.objects.filter(
        created_by=request.user
    ).order_by('-updated_at').first()
    
    if task:
        # Redirect to the annotation interface with the task ID
        return redirect('battycoda_app:annotate_task', task_id=task.id)
    else:
        # No tasks found
        messages.info(request, 'No tasks found. Please create new tasks or task batches.')
        return redirect('battycoda_app:task_list')

@login_required
def task_annotation_view(request, task_id):
    """Show the annotation interface for a specific task"""
    # Get the task
    task = get_object_or_404(Task, id=task_id, created_by=request.user)
    
    # Handle task update if form submitted
    if request.method == 'POST':
        # Check if the "mark as done" button was clicked
        if 'mark_done' in request.POST:
            label = request.POST.get('type_call', '')
            # Handle custom "other" label
            if not label and 'other_call' in request.POST:
                label = request.POST.get('other_call', '')
            
            # Update the task
            task.label = label
            task.is_done = True
            task.status = 'done'
            task.save()
            
            messages.success(request, 'Task marked as done with label: ' + label)
            
            # Redirect to the next task
            return redirect('battycoda_app:get_next_task')
    
    # Get hash of the wav file for validation 
    import hashlib
    import os
    import pickle
    from .utils import convert_path_to_os_specific
    
    # Extract the wav file information from the task
    wav_file_name = task.wav_file_name
    species = task.species
    
    # Path to the WAV file - check if it's in the media directory (uploaded file)
    if task.batch and task.batch.wav_file:
        # Get the path from the uploaded file in the batch
        wav_url = task.batch.wav_file.url
        full_path = task.batch.wav_file.path
        os_path = full_path
    else:
        # Assume the path is based on the project structure (old way)
        full_path = os.path.join(
            "home", 
            request.user.username, 
            species, 
            task.project, 
            wav_file_name
        )
        os_path = convert_path_to_os_specific(full_path)
        wav_url = f"/{full_path}"
    
    # Create hash
    file_hash = hashlib.md5(os_path.encode()).hexdigest()
    logger.info(f"Generated hash {file_hash} for path {os_path}")
    
    # Set up onset and offset as a "call"
    # In our case, we'll treat each task as one "call"
    total_calls = 1
    
    # Get call types from the database (preferred) or fall back to text file
    call_types = []
    call_descriptions = {}  # To store full descriptions for tooltips
    
    # Try to get call types from the database first
    species_obj = None
    try:
        species_obj = Species.objects.get(name=species)
        # Get calls from the database
        calls = Call.objects.filter(species=species_obj)
        if calls.exists():
            for call in calls:
                call_types.append(call.short_name)
                description = call.long_name
                if call.description:
                    description += f" - {call.description}"
                call_descriptions[call.short_name] = description
                
            logger.info(f"Loaded {len(call_types)} call types from database for species {species}")
    except Species.DoesNotExist:
        logger.warning(f"Species {species} not found in database")
    except Exception as e:
        logger.error(f"Error loading call types from database: {str(e)}")
    
    # If no call types loaded from database, try the text file as fallback
    if not call_types:
        species_text_path = os.path.join(settings.BASE_DIR, 'static', f"{species}.txt")
        if os.path.exists(species_text_path):
            try:
                with open(species_text_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            # Split at the first comma
                            parts = line.split(',', 1)
                            call_type = parts[0].strip()
                            description = parts[1].strip() if len(parts) > 1 else ""
                            
                            # Add to our lists
                            call_types.append(call_type)
                            call_descriptions[call_type] = description
                logger.info(f"Loaded {len(call_types)} call types from text file for species {species}")
            except Exception as e:
                logger.error(f"Error loading call types from text file: {str(e)}")
    
    # Create context for the template
    context = {
        'task': task,
        'username': request.user.username,
        'species': species,
        'species_obj': species_obj,  # Add the species object to the context
        'wav_path': wav_file_name,
        'full_path': full_path,
        'wav_url': wav_url,
        'file_hash': file_hash,
        'total_calls': total_calls,
        'call_types': call_types,
        'call_descriptions': call_descriptions,
        'onset': task.onset,
        'offset': task.offset
    }
    
    # Return the annotation interface
    return render(request, 'tasks/annotate_task.html', context)

@login_required
def wav_file_view(request, username, species, wav_path):
    """Legacy view for WAV file viewing - redirect to task creation"""
    # This view is kept for backward compatibility
    # Get hash of the file for validation
    import hashlib
    import os
    import pickle
    from .utils import convert_path_to_os_specific
    
    # Construct the full path
    full_path = f"home/{username}/{species}/{wav_path}"
    os_path = convert_path_to_os_specific(full_path)
    
    # Extract the project from the path (parent directory of the wav file)
    project = os.path.dirname(wav_path)
    
    # If there's no project, set it to the default
    if not project:
        project = "Default"
    
    # Create a new task if one doesn't exist
    task, created = Task.objects.get_or_create(
        wav_file_name=os.path.basename(wav_path),
        species=species,
        project=project,
        created_by=request.user,
        defaults={
            'onset': 0.0,
            'offset': 0.0,
            'status': 'pending'
        }
    )
    
    # Redirect to the task annotation view
    messages.info(request, 
        f"This interface is now task-based. A task has been {'created' if created else 'found'} for this WAV file."
    )
    return redirect('battycoda_app:annotate_task', task_id=task.id)

@login_required
def spectrogram_view(request):
    """Handle spectrogram generation and serving"""
    from .audio.views import handle_spectrogram
    return handle_spectrogram(request)

@login_required
def task_status_view(request, task_id):
    """Handle checking Celery task status"""
    from .audio.views import task_status
    return task_status(request, task_id)

@login_required
def audio_snippet_view(request):
    """Handle audio snippet generation and serving"""
    from .audio.views import handle_audio_snippet
    return handle_audio_snippet(request)

@login_required
def test_static_view(request, filename):
    """Test static file serving"""
    import os
    
    # Handle empty filename by serving broken_image.png
    if not filename:
        filename = 'broken_image.png'
        
    file_path = os.path.join(settings.STATIC_ROOT, filename)
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'))
    else:
        # Try to serve broken_image.png as a fallback
        fallback_path = os.path.join(settings.STATIC_ROOT, 'broken_image.png')
        if filename != 'broken_image.png' and os.path.exists(fallback_path):
            return FileResponse(open(fallback_path, 'rb'))
        return HttpResponse(f"File not found: {file_path}", status=404)

# Task management views
@login_required
def task_list_view(request):
    """Display list of all tasks"""
    # Get user profile
    profile = request.user.profile
    
    # Filter tasks by team if the user is in a team
    if profile.team:
        if profile.is_admin:
            # Admin sees all tasks in their team
            tasks = Task.objects.filter(team=profile.team).order_by('-created_at')
        else:
            # Regular user only sees their own tasks
            tasks = Task.objects.filter(created_by=request.user).order_by('-created_at')
    else:
        # Fallback to showing only user's tasks if no team is assigned
        tasks = Task.objects.filter(created_by=request.user).order_by('-created_at')
    
    context = {
        'tasks': tasks,
    }
    
    return render(request, 'tasks/task_list.html', context)

@login_required
def task_detail_view(request, task_id):
    """Display details of a specific task with option to update"""
    task = get_object_or_404(Task, id=task_id, created_by=request.user)
    
    if request.method == 'POST':
        form = TaskUpdateForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, 'Task updated successfully.')
            return redirect('battycoda_app:task_detail', task_id=task.id)
    else:
        form = TaskUpdateForm(instance=task)
    
    context = {
        'task': task,
        'form': form,
    }
    
    return render(request, 'tasks/task_detail.html', context)

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
    batch = get_object_or_404(TaskBatch, id=batch_id, created_by=request.user)
    tasks = Task.objects.filter(batch=batch)
    
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
            
            # Set team to user's team if not set
            if not batch.team and profile.team:
                batch.team = profile.team
            elif not batch.team:
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
                import numpy as np
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
                            import traceback
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
                import traceback
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

@login_required
def create_task_view(request):
    """Handle creation of a single task"""
    if request.method == 'POST':
        form = TaskForm(request.POST, user=request.user)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            
            # Set team to user's team if not set
            if not task.team and request.user.profile.team:
                task.team = request.user.profile.team
                
            task.save()
            
            messages.success(request, 'Task created successfully.')
            return redirect('battycoda_app:task_list')
    else:
        form = TaskForm(user=request.user)
    
    context = {
        'form': form,
    }
    
    return render(request, 'tasks/create_task.html', context)

# Species Management Views
@login_required
def species_list_view(request):
    """Display list of species"""
    # Get the user's profile
    profile = request.user.profile
    
    # Filter species by team if the user is in a team
    if profile.team:
        if profile.is_admin:
            # Admin sees all species in their team
            species_list = Species.objects.filter(team=profile.team)
        else:
            # Regular user only sees species in their team
            species_list = Species.objects.filter(team=profile.team)
    else:
        # If no team is assigned, show all species (legacy behavior)
        species_list = Species.objects.all()
    
    context = {
        'species_list': species_list,
    }
    
    return render(request, 'species/species_list.html', context)

@login_required
def species_detail_view(request, species_id):
    """Display detail of a species"""
    species = get_object_or_404(Species, id=species_id)
    
    # Get tasks for this species
    tasks = Task.objects.filter(species=species)
    
    # Get batches for this species
    batches = TaskBatch.objects.filter(species=species)
    
    # Get calls for this species
    calls = Call.objects.filter(species=species)
    
    context = {
        'species': species,
        'tasks': tasks,
        'batches': batches,
        'calls': calls,
    }
    
    return render(request, 'species/species_detail.html', context)

@login_required
def create_species_view(request):
    """Handle creation of a species with image upload and call types"""
    if request.method == 'POST':
        form = SpeciesForm(request.POST, request.FILES, user=request.user)
        call_formset = CallFormSetFactory(request.POST, prefix='calls')
        
        if form.is_valid() and call_formset.is_valid():
            # Save species
            species = form.save(commit=False)
            species.created_by = request.user
            
            # Set team to user's team if not set
            if not species.team and request.user.profile.team:
                species.team = request.user.profile.team
                
            species.save()
            
            # Keep track of calls created from file
            created_calls = set()
            
            # Process calls file if uploaded
            if form.cleaned_data.get('calls_file'):
                try:
                    calls_file = form.cleaned_data['calls_file']
                    logger.info(f"Processing calls file: {calls_file.name}, size: {calls_file.size}")
                    
                    # Read call types from file
                    lines_processed = 0
                    calls_created = 0
                    
                    # Read the content of the file
                    file_content = calls_file.read().decode('utf-8')
                    logger.info(f"File content length: {len(file_content)}")
                    
                    # Process each line
                    for line in file_content.splitlines():
                        lines_processed += 1
                        line = line.strip()
                        logger.info(f"Processing line: '{line}'")
                        
                        if line and (',' in line or '|' in line):
                            if ',' in line:
                                short_name, long_name = line.split(',', 1)
                            else:
                                short_name, long_name = line.split('|', 1)
                                
                            short_name = short_name.strip()
                            long_name = long_name.strip()
                            
                            call = Call.objects.create(
                                species=species,
                                short_name=short_name,
                                long_name=long_name
                            )
                            created_calls.add(short_name)
                            calls_created += 1
                            logger.info(f"Created call type {short_name} for species {species.name}")
                    
                    messages.success(request, f"Successfully imported {calls_created} call types from file.")
                    logger.info(f"Processed {lines_processed} lines, created {calls_created} call types")
                except Exception as e:
                    messages.error(request, f"Error processing calls file: {str(e)}")
                    logger.error(f"Error processing calls file: {str(e)}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            # Save call types from formset
            for call_form in call_formset:
                if call_form.is_valid() and call_form.cleaned_data and not call_form.cleaned_data.get('DELETE', False):
                    # Check if we have actual data and it's not a duplicate of something from the file
                    short_name = call_form.cleaned_data.get('short_name')
                    if short_name and short_name not in created_calls:
                        call = call_form.save(commit=False)
                        call.species = species
                        call.save()
            
            messages.success(request, 'Species created successfully.')
            return redirect('battycoda_app:species_detail', species_id=species.id)
    else:
        form = SpeciesForm(user=request.user)
        call_formset = CallFormSetFactory(prefix='calls')
    
    context = {
        'form': form,
        'call_formset': call_formset,
    }
    
    return render(request, 'species/create_species.html', context)

@login_required
def edit_species_view(request, species_id):
    """Handle editing of a species"""
    species = get_object_or_404(Species, id=species_id)
    calls = Call.objects.filter(species=species)
    
    if request.method == 'POST':
        form = SpeciesForm(request.POST, request.FILES, instance=species)
        call_formset = CallFormSetFactory(request.POST, prefix='calls')
        
        if form.is_valid() and call_formset.is_valid():
            # Save species
            form.save()
            
            # Keep track of calls that should not be deleted
            preserved_calls = set()
            
            # Process calls file if uploaded
            if form.cleaned_data.get('calls_file'):
                try:
                    calls_file = form.cleaned_data['calls_file']
                    logger.info(f"Processing calls file: {calls_file.name}, size: {calls_file.size}")
                    
                    # Read call types from file
                    lines_processed = 0
                    calls_created = 0
                    
                    # Read the content of the file
                    file_content = calls_file.read().decode('utf-8')
                    logger.info(f"File content length: {len(file_content)}")
                    
                    # Process each line
                    for line in file_content.splitlines():
                        lines_processed += 1
                        line = line.strip()
                        logger.info(f"Processing line: '{line}'")
                        
                        if line and (',' in line or '|' in line):
                            if ',' in line:
                                short_name, long_name = line.split(',', 1)
                            else:
                                short_name, long_name = line.split('|', 1)
                                
                            short_name = short_name.strip()
                            long_name = long_name.strip()
                            
                            # Create or update the call
                            call, created = Call.objects.get_or_create(
                                species=species,
                                short_name=short_name,
                                defaults={
                                    'long_name': long_name
                                }
                            )
                            
                            # Add to preserved calls
                            preserved_calls.add(call.id)
                            
                            # If not created, update the long name
                            if not created:
                                call.long_name = long_name
                                call.save()
                                
                            calls_created += 1
                            logger.info(f"{'Created' if created else 'Updated'} call type {short_name} for species {species.name}")
                    
                    messages.success(request, f"Successfully imported {calls_created} call types from file.")
                    logger.info(f"Processed {lines_processed} lines, created/updated {calls_created} call types")
                    
                except Exception as e:
                    messages.error(request, f"Error processing calls file: {str(e)}")
                    logger.error(f"Error processing calls file: {str(e)}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            # Save call types from formset
            for call_form in call_formset:
                if call_form.is_valid() and call_form.cleaned_data:
                    if call_form.cleaned_data.get('DELETE', False):
                        # Delete existing call if it has an ID and is marked for deletion
                        if call_form.cleaned_data.get('id'):
                            call_id = call_form.cleaned_data['id'].id
                            if call_id not in preserved_calls:
                                call_form.cleaned_data['id'].delete()
                    elif call_form.cleaned_data.get('short_name'):
                        # Create or update call
                        call = call_form.save(commit=False)
                        call.species = species
                        call.save()
                        preserved_calls.add(call.id)
            
            # Delete any calls not in the preserved set
            if preserved_calls:
                Call.objects.filter(species=species).exclude(id__in=preserved_calls).delete()
            
            messages.success(request, 'Species updated successfully.')
            return redirect('battycoda_app:species_detail', species_id=species.id)
    else:
        form = SpeciesForm(instance=species)
        
        # Initialize formset with existing calls
        call_formset = CallFormSetFactory(
            queryset=calls,
            prefix='calls'
        )
    
    context = {
        'form': form,
        'species': species,
        'call_formset': call_formset,
    }
    
    return render(request, 'species/edit_species.html', context)

# Project Management Views
@login_required
def project_list_view(request):
    """Display list of projects"""
    # Get the user's profile
    profile = request.user.profile
    
    # Filter projects by team if the user is in a team
    if profile.team:
        if profile.is_admin:
            # Admin sees all projects in their team
            project_list = Project.objects.filter(team=profile.team)
        else:
            # Regular user only sees projects in their team
            project_list = Project.objects.filter(team=profile.team)
    else:
        # If no team is assigned, show all projects (legacy behavior)
        project_list = Project.objects.all()
    
    context = {
        'project_list': project_list,
    }
    
    return render(request, 'projects/project_list.html', context)

@login_required
def project_detail_view(request, project_id):
    """Display detail of a project"""
    project = get_object_or_404(Project, id=project_id)
    
    # Get tasks for this project
    tasks = Task.objects.filter(project=project)
    
    # Get batches for this project
    batches = TaskBatch.objects.filter(project=project)
    
    context = {
        'project': project,
        'tasks': tasks,
        'batches': batches,
    }
    
    return render(request, 'projects/project_detail.html', context)

@login_required
def create_project_view(request):
    """Handle creation of a project"""
    if request.method == 'POST':
        form = ProjectForm(request.POST, user=request.user)
        if form.is_valid():
            project = form.save(commit=False)
            project.created_by = request.user
            
            # Set team to user's team if not set
            if not project.team and request.user.profile.team:
                project.team = request.user.profile.team
                
            project.save()
            
            messages.success(request, 'Project created successfully.')
            return redirect('battycoda_app:project_list')
    else:
        form = ProjectForm(user=request.user)
    
    context = {
        'form': form,
    }
    
    return render(request, 'projects/create_project.html', context)

@login_required
def edit_project_view(request, project_id):
    """Handle editing of a project"""
    project = get_object_or_404(Project, id=project_id)
    
    # Only allow editing if the user is admin or in the same team
    if request.user.profile.is_admin or (request.user.profile.team and request.user.profile.team == project.team):
        if request.method == 'POST':
            form = ProjectForm(request.POST, instance=project, user=request.user)
            if form.is_valid():
                form.save()
                
                messages.success(request, 'Project updated successfully.')
                return redirect('battycoda_app:project_detail', project_id=project.id)
        else:
            form = ProjectForm(instance=project, user=request.user)
        
        context = {
            'form': form,
            'project': project,
        }
        
        return render(request, 'projects/edit_project.html', context)
    else:
        messages.error(request, 'You do not have permission to edit this project.')
        return redirect('battycoda_app:project_list')

# Team Management Views
@login_required
def team_list_view(request):
    """Display list of teams (admin only)"""
    # Only admins can see all teams
    if request.user.profile.is_admin:
        teams = Team.objects.all()
    else:
        # Regular users only see their own team
        if request.user.profile.team:
            teams = Team.objects.filter(id=request.user.profile.team.id)
        else:
            teams = Team.objects.none()
    
    context = {
        'teams': teams,
    }
    
    return render(request, 'teams/team_list.html', context)

@login_required
def team_detail_view(request, team_id):
    """Display details of a team"""
    # Only allow viewing if the user is admin or a member of this team
    team = get_object_or_404(Team, id=team_id)
    
    if request.user.profile.is_admin or request.user.profile.team == team:
        # Get members of this team
        members = UserProfile.objects.filter(team=team)
        
        # Get projects for this team
        projects = Project.objects.filter(team=team)
        
        # Get species for this team
        species = Species.objects.filter(team=team)
        
        # Get task batches for this team
        batches = TaskBatch.objects.filter(team=team)
        
        context = {
            'team': team,
            'members': members,
            'projects': projects,
            'species': species,
            'batches': batches,
        }
        
        return render(request, 'teams/team_detail.html', context)
    else:
        messages.error(request, 'You do not have permission to view this team.')
        return redirect('battycoda_app:team_list')

@login_required
def create_team_view(request):
    """Handle creation of a team (admin only)"""
    # Only superusers or current admins can create teams
    if not request.user.is_superuser and not request.user.profile.is_admin:
        messages.error(request, 'You do not have permission to create teams.')
        return redirect('battycoda_app:home')
    
    if request.method == 'POST':
        form = TeamForm(request.POST)
        if form.is_valid():
            team = form.save()
            
            messages.success(request, 'Team created successfully.')
            return redirect('battycoda_app:team_detail', team_id=team.id)
    else:
        form = TeamForm()
    
    context = {
        'form': form,
    }
    
    return render(request, 'teams/create_team.html', context)

@login_required
def edit_team_view(request, team_id):
    """Handle editing of a team (admin only)"""
    # Only superusers or admins of this team can edit it
    team = get_object_or_404(Team, id=team_id)
    
    if not request.user.is_superuser and not (request.user.profile.is_admin and request.user.profile.team == team):
        messages.error(request, 'You do not have permission to edit this team.')
        return redirect('battycoda_app:team_list')
    
    if request.method == 'POST':
        form = TeamForm(request.POST, instance=team)
        if form.is_valid():
            form.save()
            
            messages.success(request, 'Team updated successfully.')
            return redirect('battycoda_app:team_detail', team_id=team.id)
    else:
        form = TeamForm(instance=team)
    
    context = {
        'form': form,
        'team': team,
    }
    
    return render(request, 'teams/edit_team.html', context)

@login_required
def manage_team_members_view(request, team_id):
    """Handle assigning users to teams (admin only)"""
    # Only superusers or admins of this team can manage members
    team = get_object_or_404(Team, id=team_id)
    
    if not request.user.is_superuser and not (request.user.profile.is_admin and request.user.profile.team == team):
        messages.error(request, 'You do not have permission to manage team members.')
        return redirect('battycoda_app:team_list')
    
    # Get all members of this team
    team_members = UserProfile.objects.filter(team=team)
    
    # Get all users not in this team
    non_team_users = UserProfile.objects.exclude(team=team)
    
    if request.method == 'POST':
        # Handle adding a user to the team
        if 'add_user' in request.POST:
            user_id = request.POST.get('user_id')
            if user_id:
                user_profile = get_object_or_404(UserProfile, id=user_id)
                user_profile.team = team
                user_profile.save()
                messages.success(request, f'User {user_profile.user.username} added to the team.')
        
        # Handle removing a user from the team
        elif 'remove_user' in request.POST:
            user_id = request.POST.get('user_id')
            if user_id:
                user_profile = get_object_or_404(UserProfile, id=user_id)
                user_profile.team = None
                user_profile.is_admin = False  # Remove admin status when removed from team
                user_profile.save()
                messages.success(request, f'User {user_profile.user.username} removed from the team.')
        
        # Handle toggling admin status
        elif 'toggle_admin' in request.POST:
            user_id = request.POST.get('user_id')
            if user_id:
                user_profile = get_object_or_404(UserProfile, id=user_id)
                user_profile.is_admin = not user_profile.is_admin
                user_profile.save()
                status = 'granted' if user_profile.is_admin else 'revoked'
                messages.success(request, f'Admin status {status} for user {user_profile.user.username}.')
        
        return redirect('battycoda_app:manage_team_members', team_id=team.id)
    
    context = {
        'team': team,
        'team_members': team_members,
        'non_team_users': non_team_users,
    }
    
    return render(request, 'teams/manage_members.html', context)
