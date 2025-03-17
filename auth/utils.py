"""
Authentication utility functions.
"""
import datetime
import os
import secrets
import string
import logging
import requests
import jwt
from functools import wraps
from flask import current_app, request, redirect, url_for, g
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import Forbidden

from database import db, User
from email_service import email_service

# Set up logging
logger = logging.getLogger('battability.auth.utils')

def validate_cloudflare_token(token, audience):
    """
    Validate a Cloudflare Access JWT token
    
    Args:
        token (str): JWT token from Cloudflare Access
        audience (str): The audience claim to validate
        
    Returns:
        dict or None: Decoded token payload if valid, None otherwise
    """
    try:
        # Fetch the Cloudflare Access certificates
        cf_certs_url = "https://battycoda.cloudflareaccess.com/cdn-cgi/access/certs"
        response = requests.get(cf_certs_url)
        jwks = response.json()
        
        # Decode and validate the JWT
        decoded = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=audience,
            options={"verify_exp": True}
        )
        
        # Return the decoded token
        return decoded
    except Exception as e:
        logger.error(f"Error validating Cloudflare token: {str(e)}")
        return None

def cloudflare_access_required(f):
    """
    Decorator to require Cloudflare Access authentication
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Skip if Cloudflare Access is not enabled
        if not current_app.config.get('CLOUDFLARE_ACCESS_ENABLED', False):
            return f(*args, **kwargs)
        
        # Get the Cloudflare Access JWT from the CF-Access-Jwt-Assertion header
        cf_token = request.headers.get('CF-Access-Jwt-Assertion')
        if not cf_token:
            logger.warning("Missing Cloudflare Access token")
            raise Forbidden("Cloudflare Access authentication required")
        
        # Validate the token
        audience = current_app.config.get('CLOUDFLARE_AUDIENCE', '')
        decoded_token = validate_cloudflare_token(cf_token, audience)
        if not decoded_token:
            logger.warning("Invalid Cloudflare Access token")
            raise Forbidden("Invalid Cloudflare Access token")
        
        # Store the token data for use in the view
        g.cf_user = decoded_token.get('email', '')
        
        return f(*args, **kwargs)
    return decorated_function

def create_user_account(username, email, password):
    """
    Create a new user account.
    
    Args:
        username (str): The username
        email (str): The email address
        password (str): The password
    
    Returns:
        tuple: (success, message, user_obj)
    """
    try:
        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            return False, "Username already exists", None
        
        if User.query.filter_by(email=email).first():
            return False, "Email already in use", None
        
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
        
        return True, "Registration successful!", new_user
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating user account: {str(e)}")
        return False, f"An error occurred: {str(e)}", None

def send_welcome_email(email, username):
    """
    Send a welcome email to a new user.
    
    Args:
        email (str): User's email address
        username (str): User's username
    
    Returns:
        tuple: (success, message)
    """
    try:
        success, message = email_service.send_welcome_email(email, username)
        if success:
            logger.info(f"Welcome email sent to {email}")
        else:
            logger.error(f"Failed to send welcome email: {message}")
        return success, message
    except Exception as e:
        logger.error(f"Exception sending welcome email: {str(e)}")
        return False, str(e)

def generate_password_reset_token(user):
    """
    Generate a secure password reset token and save it to the user's account.
    
    Args:
        user (User): The user object
    
    Returns:
        str: The reset token
    """
    # Generate a secure token
    token = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(50))
    
    # Set token and expiry date (24 hours from now)
    user.reset_token = token
    user.reset_token_expiry = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    db.session.commit()
    
    return token

def generate_login_code(user):
    """
    Generate a one-time login code for the user.
    
    Args:
        user (User): The user object
    
    Returns:
        str: The login code
    """
    # Generate a random 6-digit code
    import random
    login_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    
    # Set code expiry time (15 minutes from now)
    user.login_code = login_code
    user.login_code_expiry = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
    db.session.commit()
    
    return login_code

def verify_login_code(user, code):
    """
    Verify a login code for a user.
    
    Args:
        user (User): The user object
        code (str): The login code to verify
    
    Returns:
        bool: True if the code is valid, False otherwise
    """
    if (user.login_code == code and 
        user.login_code_expiry and 
        user.login_code_expiry > datetime.datetime.utcnow()):
        # Clear the login code after verification
        user.login_code = None
        user.login_code_expiry = None
        db.session.commit()
        return True
    return False

def update_user_settings(user, settings):
    """
    Update a user's settings.
    
    Args:
        user (User): The user object
        settings (dict): The settings to update
    """
    # Update user preferences
    if 'contrast' in settings:
        user.default_contrast = float(settings['contrast'])
    if 'loudness' in settings:
        user.default_loudness = float(settings['loudness'])
    if 'main_channel' in settings:
        user.default_main_channel = int(settings['main_channel'])
    if 'confidence_threshold' in settings:
        user.default_confidence_threshold = float(settings['confidence_threshold'])
    
    db.session.commit()