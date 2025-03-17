"""
Path and task handling routes for the application.
"""
import os
import pickle
import csv
import logging
from flask import render_template, redirect, url_for, request, flash
from flask_login import current_user
from markupsafe import Markup
from werkzeug.datastructures import ImmutableMultiDict

import StoreTask
import utils
import GetListing
from file_management import file_list
from task_management import get_task

# Configure logging
logger = logging.getLogger('battykoda.routes.path')

def get_user_settings():
    """
    Get settings for the current user.
    
    Returns:
        dict: User settings
    """
    # Default settings for non-authenticated users
    default_user_setting = {
        'limit_confidence': '90',
        'user_name': "",
        'contrast': '4',
        'loudness': '0.5',
        'main': '1'
    }
    
    if current_user.is_authenticated:
        return current_user.get_settings_dict()
    return default_user_setting.copy()

def handle_back(path):
    """Handle back navigation (undo)"""
    # Add a flag to request.form to indicate this is an undo operation
    
    # This will be handled in handle_batty with the 'undobutton' in request.form
    # We need to modify the request.form to include 'undobutton'
    
    # Create a modified request object with 'undobutton' set
    if not hasattr(request, '_undobutton_added'):
        request.form = ImmutableMultiDict([('undobutton', 'Undo')] + list(request.form.items()))
        request._undobutton_added = True
    
    return handle_batty(path)

def handle_batty(path):
    """Main content handler for all paths"""
    # Get user settings from authenticated user or default
    user_setting = get_user_settings()
    
    # Check if user has access to this path
    path_parts = path.strip('/').split('/')
    if path_parts[0] == 'home' and len(path_parts) > 1:
        path_username = path_parts[1]
        # Only allow access to user's own directory or admin access to all
        if path_username != current_user.username and not current_user.is_admin:
            flash("You don't have permission to access this directory", "error")
            return redirect(url_for('home'))
    
    if os.path.isdir(utils.convert_path_to_os_specific(path)):
        # File list for directory paths
        return file_list(path)
    
    if path.endswith('review.html'):
        # Process review.html files
        return handle_review_html(path)
    
    # Update user settings from form data if POST request
    if request.method == 'POST':
        user_setting = request.form.copy()
        if 'submitbutton' in request.form:
            StoreTask.store_task(path[:-1], request.form)
    
    # Properly handle species and user folders versus WAV files
    path_parts = path.strip('/').split('/')
    
    # This is a path to a folder that contains species folders, not a WAV file
    if len(path_parts) <= 3:  # /home/username/ or /home/username/species/
        return file_list(path)
    
    # Fix for path handling - keep the original path, don't convert
    logger.info(f"Task path: original path={path}")
    
    # Remove trailing slash if present
    file_path = path[:-1] if path.endswith('/') else path
    
    # For data directory structure, just use the original path
    # Don't convert from 'home' to 'Users' since data already follows a specific structure
    full_path = os.path.join(file_path)
    logger.info(f"Constructed full path: {full_path}")
    
    return get_task(
        path=path,
        user_setting=user_setting,
        undo=('undobutton' in request.form)
    )

def handle_review_html(path):
    """
    Handle review.html files for classification review.
    
    Args:
        path (str): Path to the review.html file
        
    Returns:
        str: Rendered HTML with review content
    """
    # Convert path to OS-specific format
    mod_path = utils.convert_path_to_os_specific(path)
    
    if request.method == 'POST':
        with open(mod_path + '.pickle', 'rb') as pfile:
            segment_data = pickle.load(pfile)
        type_c = path.split('/')[-1][:-12]
        for idx in range(len(segment_data['labels'])):
            if segment_data['labels'][idx]['type_call'] == type_c:
                if 'call_' + str(idx) in request.form:
                    segment_data['labels'][idx] = dict(segment_data['labels'][idx])
                    segment_data['labels'][idx]['type_call'] = 'Unsure'
        with open(mod_path + '.pickle', 'wb') as pfile:
            pickle.dump(segment_data, pfile)
        data_pre = segment_data
        data = []
        for idx in range(len(data_pre['onsets'])):
            data.append(
                [data_pre['onsets'][idx], data_pre['offsets'][idx], data_pre['labels'][idx]['type_call']])
        with open(mod_path + '.csv', 'w') as f:
            writer = csv.writer(f)
            writer.writerows(data)
            
    # Get listing from GetListing module
    return GetListing.get_listing(
        path_to_file=mod_path + path,
        path=path
    )