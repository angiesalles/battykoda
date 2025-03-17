"""
Basic authentication routes for BattyCoda application.
"""
import logging
import time
from flask import render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user

from auth import auth_bp
from auth.utils import (
    create_user_account, 
    send_welcome_email,
    verify_login_code,
)
from database import db, User

# Set up logging
logger = logging.getLogger('battykoda.auth.basic_routes')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login"""
    # Check if user is coming from logout
    coming_from_logout = request.referrer and '/logout' in request.referrer
    
    # If user is already logged in, redirect to home
    # But skip this check if coming from logout to prevent loop
    if current_user.is_authenticated and not coming_from_logout:
        # Log authentication state for debugging
        logger.info(f"Login route: User already authenticated as {current_user.username}")
        return redirect(url_for('home'))
        
    # If specifically coming from logout, force clear the session again
    if coming_from_logout:
        logger.info("LOGIN: Coming from logout, forcing session clear")
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
            if verify_login_code(user, login_code):                
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
        
        # Create user account
        success, message, new_user = create_user_account(username, email, password)
        
        if not success:
            flash(message)
            return render_template('register.html')
        
        # Send welcome email
        try:
            success, message = send_welcome_email(email, username)
            if success:
                flash('Registration successful! Please check your email for a welcome message.')
            else:
                flash('Registration successful! Please log in.')
        except Exception as e:
            flash('Registration successful! Please log in.')
            logger.error(f"Exception sending welcome email: {str(e)}")
        
        return redirect(url_for('auth.login'))
    
    return render_template('register.html')

@auth_bp.route('/logout')
def logout():  # Removed login_required to avoid any circular issues
    """Handle user logout"""
    try:
        # Print debug info
        logger.info(f"LOGOUT: User authenticated status before logout: {current_user.is_authenticated}")
        if hasattr(current_user, 'id'):
            logger.info(f"LOGOUT: User ID: {current_user.id}")
        
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
        logger.info("LOGOUT: Session cleared and logout_user called")
    except Exception as e:
        logger.error(f"LOGOUT ERROR: {str(e)}")
        flash(f"Error during logout: {str(e)}")
    
    # Redirect to login page
    return redirect('/auth/login')