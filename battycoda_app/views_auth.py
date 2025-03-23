import logging
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from .models import UserProfile, TeamInvitation, TeamMembership
from .forms import UserRegisterForm, UserLoginForm, UserProfileForm
from .utils import ensure_user_directory_exists

# Set up logging
logger = logging.getLogger('battycoda.views_auth')

def login_view(request):
    """Handle user login"""
    if request.user.is_authenticated:
        return redirect('battycoda_app:index')
    
    # Check if there's an invitation token in the session
    invitation_token = request.session.get('invitation_token')
        
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
                
                # Process invitation if there is one
                if invitation_token:
                    try:
                        invitation = TeamInvitation.objects.get(token=invitation_token)
                        if not invitation.is_expired and not invitation.accepted:
                            # Add user to team using TeamMembership model
                            membership, created = TeamMembership.objects.get_or_create(
                                user=user,
                                team=invitation.team,
                                defaults={'is_admin': False}  # New members aren't admins by default
                            )
                            
                            # Set the team from the invitation as active
                            user.profile.team = invitation.team
                            user.profile.save()
                            
                            # Mark invitation as accepted
                            invitation.accepted = True
                            invitation.save()
                            
                            # Clear the invitation token from session
                            del request.session['invitation_token']
                            
                            messages.success(
                                request, 
                                f'You have been added to the team "{invitation.team.name}".'
                            )
                    except TeamInvitation.DoesNotExist:
                        # If invitation doesn't exist, just continue with login
                        pass
                
                # Check for next parameter
                next_page = request.GET.get('next')
                if not next_page or not next_page.startswith('/'):
                    next_page = reverse('battycoda_app:index')
                
                return redirect(next_page)
        else:
            messages.error(request, 'Please check your login details and try again.')
    else:
        form = UserLoginForm()
        
    return render(request, 'auth/login.html', {'form': form})

def register_view(request):
    """Handle user registration"""
    if request.user.is_authenticated:
        return redirect('battycoda_app:index')
    
    # Check if there's an invitation token in the session
    invitation_token = request.session.get('invitation_token')
    invitation = None
    if invitation_token:
        try:
            invitation = TeamInvitation.objects.get(token=invitation_token)
            # Pre-fill email if it matches the invitation
            initial_email = invitation.email
        except TeamInvitation.DoesNotExist:
            invitation = None
            initial_email = ''
    else:
        initial_email = ''
        
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Create user's home directory from template
            ensure_user_directory_exists(user.username)
            logger.info(f"Created home directory for new user {user.username}")
            
            # If there's a valid invitation, process it
            if invitation and not invitation.is_expired and not invitation.accepted:
                # Get the user's profile
                profile = user.profile
                
                # Create team membership
                membership, created = TeamMembership.objects.get_or_create(
                    user=user,
                    team=invitation.team,
                    defaults={'is_admin': False}  # New members aren't admins by default
                )
                
                # Set the team from the invitation as active
                profile.team = invitation.team
                profile.save()
                
                # Mark invitation as accepted
                invitation.accepted = True
                invitation.save()
                
                # Clear the invitation token from session
                if 'invitation_token' in request.session:
                    del request.session['invitation_token']
                
                messages.success(
                    request, 
                    f'Registration successful! You have been added to the team "{invitation.team.name}". Please log in.'
                )
            else:
                messages.success(request, 'Registration successful! Please log in.')
                
            # Send welcome email
            # TODO: Implement email sending
            
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
    
    # Get all teams the user is a member of through TeamMembership
    team_memberships = TeamMembership.objects.filter(user=request.user).select_related('team')
    
    context = {
        'user': request.user,
        'profile': profile,
        'team_memberships': team_memberships,
        'active_team': profile.team,  # The currently active team
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