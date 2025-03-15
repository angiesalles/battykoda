"""
Authentication module for BattyCoda application.
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
import os
import secrets
import string

from database import db, User
from email_service import email_service

# Create a blueprint for authentication routes
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login"""
    # Check if user is coming from logout
    coming_from_logout = request.referrer and '/logout' in request.referrer
    
    # If user is already logged in, redirect to home
    # But skip this check if coming from logout to prevent loop
    if current_user.is_authenticated and not coming_from_logout:
        # Log authentication state for debugging
        print(f"Login route: User already authenticated as {current_user.username}")
        return redirect(url_for('home'))
        
    # If specifically coming from logout, force clear the session again
    if coming_from_logout:
        print("LOGIN: Coming from logout, forcing session clear")
        session.clear()
        logout_user()
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        login_code = request.form.get('login_code')
        remember = True if request.form.get('remember') else False
        
        # Find user by username
        user = User.query.filter_by(username=username).first()
        
        if not user:
            flash('Please check your login details and try again.')
            return render_template('login.html')
            
        # Check if using one-time code login
        if login_code:
            # Verify one-time code
            if (user.login_code == login_code and 
                user.login_code_expiry and 
                user.login_code_expiry > datetime.datetime.utcnow()):
                
                # Clear the login code after use
                user.login_code = None
                user.login_code_expiry = None
                db.session.commit()
                
                # Log in user and update last login timestamp
                login_user(user, remember=remember)
                user.update_last_login()
                
                # Get the 'next' parameter from request (if exists)
                next_page = request.args.get('next')
                
                if not next_page or not next_page.startswith('/'):
                    next_page = url_for('home')
                    
                return redirect(next_page)
            else:
                flash('Invalid or expired login code.')
                return render_template('login.html')
        
        # Otherwise check password
        elif not user.verify_password(password):
            flash('Please check your login details and try again.')
            return render_template('login.html')
        
        # Log in user and update last login timestamp
        login_user(user, remember=remember)
        user.update_last_login()
        
        # Get the 'next' parameter from request (if exists)
        next_page = request.args.get('next')
        
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('home')
            
        return redirect(next_page)
    
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Handle user registration"""
    # If user is already logged in, redirect to home
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate inputs
        if not username or not email or not password:
            flash('All fields are required')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match')
            return render_template('register.html')
        
        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already in use')
            return render_template('register.html')
        
        # Create new user
        new_user = User(
            username=username,
            email=email
        )
        new_user.password = password  # This will hash the password
        
        # Add user to database
        db.session.add(new_user)
        db.session.commit()
        
        # Create user directory if it doesn't exist
        user_dir = os.path.join('data', 'home', username)
        if not os.path.exists(user_dir):
            os.makedirs(user_dir, exist_ok=True)
        
        # Create default species directory if it doesn't exist
        species_dir = os.path.join(user_dir, 'Efuscus')
        if not os.path.exists(species_dir):
            os.makedirs(species_dir, exist_ok=True)
        
        # Send welcome email
        try:
            success, message = email_service.send_welcome_email(email, username)
            if success:
                flash('Registration successful! Please check your email for a welcome message.')
            else:
                flash('Registration successful! Please log in.')
                # Log the email failure
                current_app.logger.error(f"Failed to send welcome email: {message}")
        except Exception as e:
            flash('Registration successful! Please log in.')
            current_app.logger.error(f"Exception sending welcome email: {str(e)}")
        
        return redirect(url_for('auth.login'))
    
    return render_template('register.html')

@auth_bp.route('/logout')
def logout():  # Removed login_required to avoid any circular issues
    """Handle user logout"""
    try:
        # Print debug info
        print(f"LOGOUT: User authenticated status before logout: {current_user.is_authenticated}")
        if hasattr(current_user, 'id'):
            print(f"LOGOUT: User ID: {current_user.id}")
        
        # Try more aggressive session removal
        session.pop('_user_id', None)
        session.pop('user_id', None)
        session.pop('_id', None)
        
        # Make sure to properly log out the user
        logout_user()
        
        # Clear all session data
        session.clear()
        
        # Add a message to confirm logout
        flash('You have been logged out successfully.')
        print("LOGOUT: Session cleared and logout_user called")
    except Exception as e:
        print(f"LOGOUT ERROR: {str(e)}")
        flash(f"Error during logout: {str(e)}")
    
    # Redirect to login page
    return redirect('/auth/login')

@auth_bp.route('/profile')
@login_required
def profile():
    """Display user profile"""
    return render_template('profile.html')

@auth_bp.route('/request-login-code', methods=['GET', 'POST'])
def request_login_code():
    """Request a one-time login code"""
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        
        # Find user by email
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Generate a random 6-digit code
            import random
            login_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            
            # Set code expiry time (15 minutes from now)
            user.login_code = login_code
            user.login_code_expiry = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
            db.session.commit()
            
            # Send email with the code
            try:
                success, message = email_service.send_login_code_email(
                    user.email, user.username, login_code)
                if success:
                    flash('A login code has been sent to your email address.')
                else:
                    flash('Failed to send login code. Please try again later.')
                    current_app.logger.error(f"Failed to send login code email: {message}")
            except Exception as e:
                flash('Failed to send login code. Please try again later.')
                current_app.logger.error(f"Exception sending login code email: {str(e)}")
        else:
            # Don't reveal that the email doesn't exist for security reasons
            import time
            time.sleep(1)
        
        # Always show success message, even if user doesn't exist (security best practice)
        flash('If your email address exists in our database, you will receive a login code shortly.')
        return redirect(url_for('auth.login'))
    
    return render_template('request_login_code.html')

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Handle forgotten passwords."""
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        
        # Find user by email
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Generate a secure token
            token = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(50))
            
            # Set token and expiry date (24 hours from now)
            user.reset_token = token
            user.reset_token_expiry = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
            db.session.commit()
            
            # Create reset link
            # In production, use proper absolute URLs with domain
            reset_link = url_for('auth.reset_password', token=token, _external=True)
            
            # Send reset email
            try:
                success, message = email_service.send_password_reset_email(
                    user.email, user.username, reset_link)
                if success:
                    flash('Password reset instructions have been sent to your email address.')
                else:
                    flash('Failed to send password reset email. Please try again later.')
                    current_app.logger.error(f"Failed to send password reset email: {message}")
            except Exception as e:
                flash('Failed to send password reset email. Please try again later.')
                current_app.logger.error(f"Exception sending password reset email: {str(e)}")
        else:
            # Don't reveal that the email doesn't exist for security reasons
            # But wait a bit to prevent timing attacks
            import time
            time.sleep(1)
            
        # Always show success message, even if user doesn't exist (security best practice)
        flash('If your email address exists in our database, you will receive a password recovery link at your email address.')
        return redirect(url_for('auth.login'))
        
    return render_template('forgot_password.html')

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password using a valid token."""
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    # Find user by token
    user = User.query.filter_by(reset_token=token).first()
    
    # Check if token is valid and not expired
    if not user or not user.reset_token_expiry or user.reset_token_expiry < datetime.datetime.utcnow():
        flash('The password reset link is invalid or has expired.')
        return redirect(url_for('auth.forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate inputs
        if not password or not confirm_password:
            flash('Please enter a new password.')
            return render_template('reset_password.html', token=token)
        
        if password != confirm_password:
            flash('Passwords do not match.')
            return render_template('reset_password.html', token=token)
        
        # Update password and clear reset token
        user.password = password
        user.reset_token = None
        user.reset_token_expiry = None
        db.session.commit()
        
        flash('Your password has been updated! You can now log in with your new password.')
        return redirect(url_for('auth.login'))
    
    return render_template('reset_password.html', token=token)

@auth_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Edit user profile"""
    if request.method == 'POST':
        # Update user preferences
        current_user.default_contrast = float(request.form.get('contrast', 0.5))
        current_user.default_loudness = float(request.form.get('loudness', 0.8))
        current_user.default_main_channel = int(request.form.get('main_channel', 1))
        current_user.default_confidence_threshold = float(request.form.get('confidence_threshold', 70.0))
        
        # Update email if provided
        new_email = request.form.get('email')
        if new_email and new_email != current_user.email:
            # Check if email is already in use
            if User.query.filter_by(email=new_email).first():
                flash('Email already in use')
            else:
                current_user.email = new_email
        
        # Update password if provided
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password:
            if new_password != confirm_password:
                flash('Passwords do not match')
            else:
                current_user.password = new_password
        
        # Commit changes to database
        db.session.commit()
        flash('Profile updated successfully')
        return redirect(url_for('auth.profile'))
    
    return render_template('edit_profile.html')