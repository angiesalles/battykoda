"""
Directory and navigation routes for the application.
"""
import os
import platform
import getpass
from flask import render_template, redirect, url_for, session, request, flash, g, current_app
from flask_login import current_user, login_required, logout_user
from markupsafe import Markup
import logging

import htmlGenerator
import utils
from file_management import file_list
from auth.utils import cloudflare_access_required

# Configure logging
logger = logging.getLogger('battykoda.routes.directory')

@cloudflare_access_required
def mainpage():
    """Main landing page"""
    # Check if Cloudflare Access provides user info and auto-login is enabled
    if hasattr(g, 'cf_user') and g.cf_user and current_app.config.get('CLOUDFLARE_ACCESS_ENABLED'):
        # Auto-login based on Cloudflare user
        email = g.cf_user
        
        # If the user is already authenticated, check if the emails match
        if current_user.is_authenticated:
            if current_user.email == email:
                # Emails match, proceed to home page
                return redirect(url_for('home'))
        
        # Try to find user by email
        from database import User
        user = User.query.filter_by(email=email).first()
        if user:
            # Auto login user (flask_login)
            from flask_login import login_user
            login_user(user)
            logger.info(f"Auto-logged in user {user.username} via Cloudflare Access")
            return redirect(url_for('home'))
    
    # Redirect to login if not authenticated
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    
    # If authenticated, proceed to home page
    return redirect(url_for('home'))

def main_login():
    """Direct login route for compatibility with legacy logout"""
    print("MAIN LOGIN: Direct access")
    # Force session clear if coming from logout
    if request.referrer and '/logout' in request.referrer:
        print("MAIN LOGIN: Coming from logout, clearing session")
        session.clear()
    
    # Redirect to auth login
    return redirect(url_for('auth.login'))

def legacy_logout():
    """Legacy direct logout route for compatibility"""
    print("LEGACY LOGOUT: Accessed directly")
    
    # Force session end
    if hasattr(current_user, 'id'):
        print(f"LEGACY LOGOUT: Current user ID: {current_user.id}")
    else:
        print("LEGACY LOGOUT: No current user ID")
    
    # Clear all session vars
    session.clear()
    logout_user()
    
    # Add a message
    flash('You have been logged out via legacy route.')
    print("LEGACY LOGOUT: Redirecting to login")
    
    # Direct redirect
    return redirect('/login')

def home():
    """Home page with user directories and species info"""
    # Get available species and generate links
    available_species = htmlGenerator.available_species()
    species_links = ""
    
    # Add a section for user directories
    species_links += '<li><b>User Directories:</b></li>'
    
    # Add a link to the current user's directory
    username = current_user.username
    species_links += f'<li><a href="/home/{username}/"><strong>Your Directory</strong> ({username})</a></li>'
    
    # If user is admin, show all users' directories
    if current_user.is_admin:
        from database import User
        all_users = User.query.filter(User.username != username).order_by(User.username).all()
        if all_users:
            for user in all_users:
                species_links += f'<li><a href="/home/{user.username}/">{user.username}</a></li>'
    
    # Add available species templates section
    if available_species:
        species_links += '<li><b>Available Species Templates:</b></li>'
        for species in available_species:
            # Link to species info page instead of directly to species folder
            species_links += f'<li><a href="/species_info/{species}">{species}</a></li>'
    else:
        species_links += '<li>No species templates available. Please check the static folder.</li>'
    
    return render_template('welcometoBC.html', species_links=species_links, user=current_user)

def species_info(species_name):
    """Display information about a specific species template"""
    
    # Check if species template exists
    all_species = htmlGenerator.available_species()
    if species_name not in all_species:
        # Species not found
        return render_template('listBC.html', 
                              data={'listicle': Markup(f'<li>Species template "{species_name}" not found</li><li><a href="/">Return to home page</a></li>')})
    
    # Read the species text file
    species_content = ""
    call_types = []
    
    try:
        with open(f"static/{species_name}.txt") as f:
            lines = f.readlines()
            
            # Parse the call types
            for line in lines:
                if ',' in line:
                    call_type, description = line.strip().split(',', 1)
                    call_types.append({
                        'name': call_type.strip(),
                        'description': description.strip()
                    })
    except Exception as e:
        # Error reading species file
        return render_template('listBC.html', 
                              data={'listicle': Markup(f'<li>Error reading species data: {str(e)}</li><li><a href="/">Return to home page</a></li>')})
    
    # Check if image exists
    image_path = f"/static/{species_name}.jpg"
    
    # Get current username for project creation links and list all users
    current_username = current_user.username if current_user.is_authenticated else getpass.getuser()
    
    # Generate HTML for the species info page
    content = f"""
    <div style="margin: 20px; padding: 20px; background-color: #fff; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
        <h2 style="color: #2c3e50; border-bottom: 2px solid #e67e22; padding-bottom: 10px;">Species Template: {species_name}</h2>
        
        <div style="display: flex; flex-wrap: wrap; margin-bottom: 20px;">
            <div style="flex: 1; min-width: 300px; margin-right: 20px; margin-bottom: 20px;">
                <div style="border: 1px solid #ddd; padding: 10px; border-radius: 5px;">
                    <img src="{image_path}" alt="{species_name}" style="max-width: 100%; border-radius: 5px;">
                </div>
            </div>
            <div style="flex: 2; min-width: 300px;">
                <h3 style="color: #3498db; margin-top: 0;">Call Types:</h3>
                <table border="0" cellpadding="8" style="border-collapse: collapse; width: 100%; border: 1px solid #ddd; border-radius: 5px; overflow: hidden;">
                    <tr style="background-color: #3498db; color: white;">
                        <th style="text-align: left; padding: 12px 15px;">Call Type</th>
                        <th style="text-align: left; padding: 12px 15px;">Description</th>
                    </tr>
    """
    
    # Add each call type to the table with alternating row colors
    for i, call in enumerate(call_types):
        bg_color = "#f9f9f9" if i % 2 == 0 else "#fff"
        content += f"""
        <tr style="background-color: {bg_color};">
            <td style="padding: 12px 15px; border-top: 1px solid #ddd;"><strong>{call['name']}</strong></td>
            <td style="padding: 12px 15px; border-top: 1px solid #ddd;">{call['description']}</td>
        </tr>
        """
    
    content += """
                </table>
            </div>
        </div>
        
        <div style="margin-top: 30px; background-color: #f8f9fa; padding: 20px; border-radius: 5px; border-left: 4px solid #2ecc71;">
            <h3 style="color: #2c3e50; margin-top: 0;">Create New Project with This Template:</h3>
    """
    
    # Get all user directories from the system
    other_users = []
    try:
        if platform.system() == "Darwin":  # macOS
            user_dir = "/Users"
            users = os.listdir(user_dir)
            # Filter out system directories and dotfiles
            other_users = [u for u in users if not u.startswith('.') and u != 'Shared' and u != current_username]
            other_users.sort()
    except:
        pass
    
    content += f"""
            <p>Click below to navigate to this species template in your user directory:</p>
            <p><a href="/home/{current_username}/{species_name}/" class="button" style="display: inline-block; padding: 12px 20px; background-color: #2ecc71; color: white; text-decoration: none; border-radius: 5px; font-weight: bold; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">Open in Your Directory ({current_username})</a></p>
    """
    
    if other_users and current_user.is_authenticated and current_user.is_admin:
        content += """
            <p style="margin-top: 20px;">Or open in another user directory:</p>
            <div style="display: flex; flex-wrap: wrap; gap: 10px;">
        """
        
        for user in other_users:
            content += f"""
                <a href="/home/{user}/{species_name}/" style="display: inline-block; padding: 8px 15px; background-color: #3498db; color: white; text-decoration: none; border-radius: 5px; margin-bottom: 10px;">{user}</a>
            """
            
        content += """
            </div>
        """
    
    content += """
        </div>
        
        <div style="margin-top: 30px; text-align: center; border-top: 1px solid #eee; padding-top: 20px;">
            <a href="/" style="display: inline-block; padding: 10px 20px; background-color: #95a5a6; color: white; text-decoration: none; border-radius: 5px; margin-right: 10px;">Return to Home Page</a>
            <a href="/home/" style="display: inline-block; padding: 10px 20px; background-color: #95a5a6; color: white; text-decoration: none; border-radius: 5px;">Browse All Users</a>
        </div>
    </div>
    """
    
    return render_template('listBC.html', data={'listicle': Markup(content)})