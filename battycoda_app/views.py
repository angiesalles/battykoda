import logging
import os
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

from .forms import UserRegisterForm, UserLoginForm, UserProfileForm
from .models import UserProfile

# Set up logging
logger = logging.getLogger('battycoda.views')

# Basic views
def index(request):
    """Main entry point that redirects based on auth status"""
    if request.user.is_authenticated:
        return redirect('battycoda_app:home')
    return redirect('battycoda_app:login')

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
        form = UserProfileForm(request.POST, instance=profile)
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
        form = UserProfileForm(instance=profile)
        
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
def wav_file_view(request, username, species, wav_path):
    """Handle WAV file viewing - showing the annotation interface"""
    # Get hash of the file for validation
    import hashlib
    import os
    import pickle
    from .utils import convert_path_to_os_specific
    
    # Construct the full path
    full_path = f"home/{username}/{species}/{wav_path}"
    os_path = convert_path_to_os_specific(full_path)
    
    # Create hash
    # Use a simple hash based just on the path for consistency
    # This avoids file reading errors and hash mismatches across containers
    file_hash = hashlib.md5(os_path.encode()).hexdigest()
    logger.info(f"Generated hash {file_hash} for path {os_path}")
    
    # Get the number of calls from the pickle file
    pickle_path = os_path + '.pickle'
    total_calls = 5  # Default fallback value
    
    try:
        if os.path.exists(pickle_path):
            with open(pickle_path, 'rb') as pfile:
                segment_data = pickle.load(pfile)
                if 'onsets' in segment_data:
                    total_calls = len(segment_data['onsets'])
                    logger.info(f"Found {total_calls} calls in pickle file")
                else:
                    logger.warning(f"No 'onsets' found in pickle file: {pickle_path}")
        else:
            logger.warning(f"Pickle file not found: {pickle_path}")
    except Exception as e:
        logger.error(f"Error loading pickle file {pickle_path}: {str(e)}")
    
    # Get call types from the species text file
    call_types = []
    call_descriptions = {}  # To store full descriptions for tooltips
    species_text_path = os.path.join(settings.BASE_DIR, 'static', f"{species}.txt")
    
    # Debug log the path and existence
    logger.info(f"Looking for species text file at: {species_text_path}")
    logger.info(f"File exists: {os.path.exists(species_text_path)}")
    
    if os.path.exists(species_text_path):
        try:
            with open(species_text_path, 'r') as f:
                content = f.read()
                logger.info(f"File content: {content[:100]}...")  # Log first 100 chars
                
                # Re-open to process line by line
                f.seek(0)
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
                        
            logger.info(f"Loaded {len(call_types)} call types: {call_types}")
        except Exception as e:
            logger.error(f"Error loading call types: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
    else:
        logger.warning(f"Species text file not found: {species_text_path}")
    
    # Create context for the template
    context = {
        'username': username,
        'species': species,
        'wav_path': wav_path,
        'full_path': full_path,
        'file_hash': file_hash,
        'total_calls': total_calls,
        'call_types': call_types,
        'call_descriptions': call_descriptions
    }
    
    # Return the annotation interface
    return render(request, 'wav_view.html', context)

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
    file_path = os.path.join(settings.STATIC_ROOT, filename)
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'))
    else:
        return HttpResponse(f"File not found: {file_path}", status=404)
