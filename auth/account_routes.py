"""
Account management routes for BattyCoda application.
"""
import logging
import time
import datetime
from flask import render_template, redirect, url_for, request, flash, current_app
from flask_login import login_required, current_user

from auth import auth_bp
from auth.utils import (
    generate_password_reset_token,
    generate_login_code,
    update_user_settings
)
from database import db, User
from email_service import email_service

# Set up logging
logger = logging.getLogger('battykoda.auth.account_routes')

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
            # Generate a login code
            login_code = generate_login_code(user)
            
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
            # Generate token
            token = generate_password_reset_token(user)
            
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
        settings = {
            'contrast': request.form.get('contrast', 0.5),
            'loudness': request.form.get('loudness', 0.8),
            'main_channel': request.form.get('main_channel', 1),
            'confidence_threshold': request.form.get('confidence_threshold', 70.0)
        }
        
        update_user_settings(current_user, settings)
        
        # Update email if provided
        new_email = request.form.get('email')
        if new_email and new_email != current_user.email:
            # Check if email is already in use
            if User.query.filter_by(email=new_email).first():
                flash('Email already in use')
            else:
                current_user.email = new_email
                db.session.commit()
        
        # Update password if provided
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password:
            if new_password != confirm_password:
                flash('Passwords do not match')
            else:
                current_user.password = new_password
                db.session.commit()
        
        flash('Profile updated successfully')
        return redirect(url_for('auth.profile'))
    
    return render_template('edit_profile.html')