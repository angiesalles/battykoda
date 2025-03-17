"""
Basic authentication routes for BattyCoda application.
"""
import logging
import time
from flask import render_template, redirect, url_for, request, flash, session, g
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
    
    # First check for Cloudflare Access authentication
    if not coming_from_logout and request.method == 'GET':
        # If Cloudflare Access is enabled, check for Cloudflare authentication
        import os
        if os.environ.get('CLOUDFLARE_ACCESS_ENABLED') == 'True':
            # Import here to avoid circular imports
            from auth.cloudflare_verify import verify_cloudflare_jwt
            from auth.utils import create_user_account
            from flask import current_app, g
            
            # Verify JWT token
            jwt_payload = verify_cloudflare_jwt()
            if jwt_payload:
                # Get user email from JWT
                email = jwt_payload.get('email')
                if email:
                    # Find or create user by email
                    user = User.query.filter_by(email=email).first()
                    
                    # Create the user if they don't exist
                    if not user:
                        logger.info(f"Creating new user account for Cloudflare user: {email}")
                        username = email.split('@')[0].replace('.', '_')  # Simple username from email
                        success, _, user = create_user_account(
                            username=username, 
                            email=email, 
                            is_cloudflare_user=True
                        )
                        if not success or not user:
                            logger.error(f"Failed to create user account for Cloudflare user: {email}")
                            flash("Failed to create user account. Please contact support.")
                            return render_template('login.html')
                    
                    # Log the user in with Flask-Login
                    login_user(user)
                    
                    # Store Cloudflare user info for this request
                    g.cf_user = email
                    g.cf_user_id = jwt_payload.get('sub')
                    g.cf_user_data = jwt_payload
                    
                    logger.info(f"Login route: Auto-logged in Cloudflare user {user.email}")
                    return redirect(url_for('home'))
    
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

@auth_bp.route('/cloudflare-login')
def cloudflare_login():
    """Special endpoint just for Cloudflare login/debug"""
    import os
    if os.environ.get('CLOUDFLARE_ACCESS_ENABLED') != 'True':
        logger.info("Cloudflare access not enabled")
        flash("Cloudflare access not enabled on this server")
        return redirect(url_for('auth.login'))
    
    # Import verification function
    from auth.cloudflare_verify import verify_cloudflare_jwt, verify_cloudflare_headers
    
    # Check for Cloudflare headers
    has_cf_headers = verify_cloudflare_headers()
    if not has_cf_headers:
        logger.warning("No Cloudflare headers detected")
        flash("This request doesn't appear to be coming through Cloudflare")
        return redirect(url_for('auth.login'))
    
    # Verify JWT
    jwt_payload = verify_cloudflare_jwt()
    if not jwt_payload:
        logger.warning("No valid Cloudflare JWT found")
        flash("No valid Cloudflare authentication found")
        return redirect(url_for('auth.login'))
    
    # Get user info
    email = jwt_payload.get('email')
    if not email:
        logger.warning("No email in Cloudflare JWT")
        flash("Cloudflare JWT is missing required user information")
        return redirect(url_for('auth.login'))
    
    # Find or create user
    from auth.utils import create_user_account
    from database import User
    
    user = User.query.filter_by(email=email).first()
    if not user:
        logger.info(f"Creating new account for Cloudflare user: {email}")
        username = email.split('@')[0].replace('.', '_')
        success, msg, user = create_user_account(
            username=username,
            email=email,
            is_cloudflare_user=True
        )
        if not success or not user:
            logger.error(f"Failed to create user: {msg}")
            flash(f"Failed to create user account: {msg}")
            return redirect(url_for('auth.login'))
    
    # Login the user
    from flask_login import login_user
    login_user(user)
    
    # Store Cloudflare user info in g
    from flask import g
    g.cf_user = email
    g.cf_user_id = jwt_payload.get('sub')
    g.cf_user_data = jwt_payload
    
    logger.info(f"Successfully logged in Cloudflare user: {email}")
    flash(f"Welcome {user.username}! You've been logged in via Cloudflare.")
    return redirect(url_for('home'))

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
        
        # Check if this is a Cloudflare user
        is_cloudflare_user = current_user.is_authenticated and hasattr(current_user, 'is_cloudflare_user') and current_user.is_cloudflare_user
        
        # Make sure to properly log out the user
        logout_user()
        
        # Clear all session data
        session.clear()
        
        # Set up response to clear cookies
        if is_cloudflare_user:
            logger.info("LOGOUT: Cloudflare user detected")
            
            # Clear the Cloudflare cookies but stay on the site
            # Instead of redirecting to Cloudflare logout which can break the flow
            # just clear the application session and let the user re-authenticate
            # next time they interact with a protected page
            
            # Add a message for users
            flash('You have been logged out. You may need to refresh your browser to log in again with Cloudflare.')
            logger.info("LOGOUT: Cleared session for Cloudflare user")
            
            # Just redirect to login page
            return redirect('/auth/login')
        else:
            # Add a message to confirm logout
            flash('You have been logged out successfully.')
            logger.info("LOGOUT: Session cleared and logout_user called")
            # Redirect to login page
            return redirect('/auth/login')
    except Exception as e:
        logger.error(f"LOGOUT ERROR: {str(e)}")
        flash(f"Error during logout: {str(e)}")
        return redirect('/auth/login')