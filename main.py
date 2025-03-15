import os
import sys
import logging
import traceback
from flask import Flask, render_template, request, send_file, url_for, redirect, flash, session
from markupsafe import Markup
import scipy.signal
import scipy.io
from os.path import exists
import FileList
import GetAudioBit
import platform
import threading
import queue
import SoftCreateFolders
import StoreTask
import GetTask
from AppropriateFile import appropriate_file
import Workers
import Hwin
import htmlGenerator
import GetListing
from datetime import datetime
import pickle
import csv
import getpass
from flask_login import LoginManager, current_user, login_required, logout_user

# Import utility functions
import utils

# Import auth module and database models
from auth import auth_bp
from database import db, User

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('debug.log', mode='a')
    ]
)
logger = logging.getLogger('battykoda')

# Set appropriate OS folder and system-specific paths
computer_system = platform.system()
if computer_system == 'Windows':
    osfolder = '.\\data\\'
else:  # macOS or Linux
    osfolder = '/'

# Get the home directory path for the current OS
home_path = utils.get_home_directory()

app = Flask(__name__, static_folder='static')

# Configure the Flask app
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'battycoda-secret-key-development')
# Use absolute path for database location
db_path = os.path.join(os.getcwd(), 'battycoda.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy with the app
db.init_app(app)

# Initialize LoginManager
login_manager = LoginManager()
login_manager.login_view = 'auth.login'  # Flask-Login knows to prepend the blueprint URL prefix
login_manager.init_app(app)

# Register auth blueprint
app.register_blueprint(auth_bp, url_prefix='/auth')

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Default settings for non-authenticated users
default_user_setting = {
    'limit_confidence': '90',
    'user_name': "",
    'contrast': '4',
    'loudness': '0.5',
    'main': '1'
}

# Function to get settings for the current user
def get_user_settings():
    if current_user.is_authenticated:
        return current_user.get_settings_dict()
    return default_user_setting.copy()

# Global user setting (retained for backward compatibility)
global_user_setting = default_user_setting.copy()

# Create a custom filter to handle image paths and add debugging
@app.template_filter('debug_image')
def debug_image_filter(img_path):
    """
    Create an image tag with error handling and debugging information.
    This helps identify missing images.
    
    Args:
        img_path: Path to the image
        
    Returns:
        Safe HTML with the image and debug info
    """
    # Extract relevant info for debugging
    path_parts = img_path.split('?')[0].split('/')
    img_type = path_parts[-2] if len(path_parts) > 1 else "unknown"
    img_name = path_parts[-1] if path_parts else "unknown"
    
    # Full HTML for image with error handling
    html = f"""
    <div class="image-container" style="position: relative; display: inline-block;">
        <img src="{img_path}" onerror="this.onerror=null; this.src='/static/broken_image.png'; this.style.border='2px solid red'; this.parentNode.classList.add('broken-image'); console.log('Broken image: {img_path}');" />
        <div class="debug-info" style="display: none; position: absolute; top: 0; left: 0; background: rgba(255,0,0,0.7); color: white; padding: 2px; font-size: 10px;">
            Path: {img_path}
        </div>
    </div>
    """
    
    # Log for server-side debugging
    print(f"Rendering image: {img_path}")
    
    return Markup(html)

global_request_queue = queue.PriorityQueue()
global_work_queue = queue.PriorityQueue()



def initialize_app():
    """Initialize the app by starting worker threads and creating necessary directories"""
    # Verify database exists and is correctly initialized
    try:
        # Perform a quick database check within the app context
        with app.app_context():
            # Try a simple query to verify database connection
            user_count = User.query.count()
            logger.info(f"Database check: Users table exists with {user_count} users")
    except Exception as e:
        logger.error(f"Database check failed: {str(e)}")
        logger.error("This might indicate the database wasn't properly initialized. Try running ensure_db.py first.")
        # We'll continue anyway since ensure_db.py should have been run before main.py
    
    # Create necessary directories if they don't exist
    os.makedirs('data/home', exist_ok=True)
    os.makedirs('static/tempdata', exist_ok=True)
    
    # Check if this is Replit and create sample data if needed
    if os.environ.get('REPL_SLUG') or os.environ.get('REPL_ID'):
        # Copy example species file if it doesn't exist in the right location
        if os.path.exists('static/Efuscus.jpg') and os.path.exists('static/Efuscus.txt'):
            logger.info("Sample species files found. Replit setup complete.")
        else:
            logger.warning("Sample species files not found in static directory. Check repository contents.")
    
    # Start worker threads
    threading.Thread(target=Workers.worker,
                     args=(global_request_queue, global_work_queue, osfolder),
                     daemon=True).start()
    threading.Thread(target=Workers.worker2,
                     args=(global_work_queue, ),
                     daemon=True).start()

def mainfunction():
    """Run the main application server"""
    # Initialize the app
    initialize_app()
    
    # Get port and debug settings from environment variables for Replit compatibility
    port = int(os.environ.get('PORT', 8060))
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
    
    # Start the server
    app.run(host='0.0.0.0', debug=debug_mode, port=port)


@app.route('/')
def mainpage():
    """Main landing page"""
    # Redirect to login if not authenticated
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    
    # If authenticated, proceed to home page
    return redirect(url_for('home'))

@app.route('/login')
def main_login():
    """Direct login route for compatibility with legacy logout"""
    print("MAIN LOGIN: Direct access")
    # Force session clear if coming from logout
    if request.referrer and '/logout' in request.referrer:
        print("MAIN LOGIN: Coming from logout, clearing session")
        session.clear()
    
    # Redirect to auth login
    return redirect(url_for('auth.login'))

# Direct logout route for legacy compatibility
@app.route('/logout')
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

@app.route('/home')
@login_required
def home():
    """Home page with user directories and species info"""
    # Get available species and generate links
    available_species = htmlGenerator.available_species()
    species_links = ""
    
    # Add a section for user directories
    species_links += '<li><b>User Directories:</b></li>'
    
    # Add a link to the current user's directory
    username = current_user.username
    species_links += f'<li><a href="/battycoda/home/{username}/"><strong>Your Directory</strong> ({username})</a></li>'
    
    # If user is admin, show all users' directories
    if current_user.is_admin:
        all_users = User.query.filter(User.username != username).order_by(User.username).all()
        if all_users:
            for user in all_users:
                species_links += f'<li><a href="/battycoda/home/{user.username}/">{user.username}</a></li>'
    
    # Add available species templates section
    if available_species:
        species_links += '<li><b>Available Species Templates:</b></li>'
        for species in available_species:
            # Link to species info page instead of directly to species folder
            species_links += f'<li><a href="/species_info/{species}">{species}</a></li>'
    else:
        species_links += '<li>No species templates available. Please check the static folder.</li>'
    
    return render_template('welcometoBC.html', species_links=species_links, user=current_user)


@app.route('/battycoda/<path:path>', methods=['POST', 'GET'])
@login_required
def handle_batty(path):
    global global_user_setting
    
    # Get user settings from authenticated user or default
    user_setting = get_user_settings()
    
    try:
        # Use utility function to convert path to OS-specific format
        modified_path = utils.convert_path_to_os_specific(path)
    except Exception as e:
        # Handle any unexpected errors in path modification
        print(f"Error processing path {path}: {str(e)}")
        modified_path = path  # Fall back to original path if there's an error
    
    # Check if user has access to this path
    path_parts = path.strip('/').split('/')
    if path_parts[0] == 'home' and len(path_parts) > 1:
        path_username = path_parts[1]
        # Only allow access to user's own directory or admin access to all
        if path_username != current_user.username and not current_user.is_admin:
            flash("You don't have permission to access this directory", "error")
            return redirect(url_for('home'))
    
    
    if os.path.isdir(osfolder + modified_path):
        return FileList.file_list(osfolder, modified_path, path)
    if path.endswith('review.html'):
        if request.method == 'POST':
            # Convert path to OS-specific format
            mod_path = utils.convert_path_to_os_specific(path)
            path_to_file = osfolder + '/'.join(mod_path.split('/')[:-1])
            with open(path_to_file + '.pickle', 'rb') as pfile:
                segment_data = pickle.load(pfile)
            type_c = path.split('/')[-1][:-12]
            for idx in range(len(segment_data['labels'])):
                if segment_data['labels'][idx]['type_call'] == type_c:
                    if 'call_' + str(idx) in request.form:
                        segment_data['labels'][idx] = dict(segment_data['labels'][idx])
                        segment_data['labels'][idx]['type_call'] = 'Unsure'
            with open(path_to_file + '.pickle', 'wb') as pfile:
                pickle.dump(segment_data, pfile)
            data_pre = segment_data
            data = []
            for idx in range(len(data_pre['onsets'])):
                data.append(
                    [data_pre['onsets'][idx], data_pre['offsets'][idx], data_pre['labels'][idx]['type_call']])
            with open(path_to_file + '.csv', 'w') as f:
                writer = csv.writer(f)
                writer.writerows(data)
        return GetListing.get_listing(path_to_file=osfolder + path,
                                      osfolder=osfolder,
                                      path=path)
    if request.method == 'POST':
        user_setting = request.form.copy()
        if 'submitbutton' in request.form:
            StoreTask.store_task(osfolder + path[:-1], request.form)
    # Properly handle species and user folders versus WAV files
    path_parts = path.strip('/').split('/')
    
    # This is a path to a folder that contains species folders, not a WAV file
    if len(path_parts) <= 3:  # /home/username/ or /home/username/species/
        return FileList.file_list(osfolder, modified_path, path)
    
    # Convert path to OS-specific format
    mod_path = utils.convert_path_to_os_specific(path)
    return GetTask.get_task(path_to_file=osfolder + mod_path[:-1],
                            path=path,  # Keep original path for URLs
                            user_setting=user_setting,
                            osfolder=osfolder,
                            undo=('undobutton' in request.form))


@app.route('/img/<path:path>', methods=['GET'])
@login_required
def handle_image(path):
    """
    Handle image generation and serving for bat call spectrograms.
    
    Args:
        path: The URL path to the image
        
    Returns:
        Flask response with the image
    """
    # Convert path to OS-specific format
    mod_path = utils.convert_path_to_os_specific(path)
    
    # Log the request details for debugging
    logger.info(f"Image request received: {path}")
    logger.debug(f"Original path: {path}, Modified path: {mod_path}")
    logger.debug(f"Arguments: {request.args}")
    
    try:
        # Make sure required arguments are present
        required_args = ['channel', 'call', 'numcalls', 'hash', 'overview']
        for arg in required_args:
            if arg not in request.args:
                logger.error(f"Missing required argument: {arg}")
                return create_error_image(f"Missing required argument: {arg}")
        
        # Try both path formats to handle any legacy paths
        # First with the original path
        file_path = appropriate_file(path, request.args, osfolder)
        
        # Also try with the modified path
        alt_file_path = appropriate_file(mod_path, request.args, osfolder)
        
        # Log paths being checked
        logger.debug(f"Checking main path: {file_path}")
        logger.debug(f"Checking alternate path: {alt_file_path}")
        
        # Check if either path exists
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            logger.info(f"Cache hit! Using existing image at primary path: {file_path}")
            return send_file(file_path)
        elif os.path.exists(alt_file_path) and os.path.getsize(alt_file_path) > 0:
            logger.info(f"Cache hit! Using existing image at alternate path: {alt_file_path}")
            return send_file(alt_file_path)
            
        # Ensure directories exist for both paths
        folder_path = appropriate_file(mod_path, request.args, osfolder, folder_only=True)
        if not os.path.exists(folder_path):
            logger.info(f"Creating cache directory: {folder_path}")
            os.makedirs(folder_path, exist_ok=True)
            
        # Image doesn't exist, need to generate it
        logger.info(f"Cache miss. Need to generate image: {file_path}")
        
        # Set priority based on channel and overview status
        priority_part = 0 if int(request.args['channel']) == int(global_user_setting['main'])-1 else 2
        overview_part = 1 if request.args['overview'] == '1' else 0
        workload = {'path': mod_path, 'args': request.args}
        
        # Log the workload
        logger.debug(f"Putting into request queue: {mod_path}")
        
        # Add to processing queue
        global_request_queue.put(Workers.PrioItem(priority_part + overview_part, workload))
        
        # Preload next call if needed
        call_to_do = int(request.args['call'])
        if call_to_do + 1 < int(request.args['numcalls']):
            new_args = request.args.copy()
            new_args['call'] = str(call_to_do+1)
            global_request_queue.put(Workers.PrioItem(4 + priority_part, {'path': mod_path, 'args': new_args}))
            
        # Wait for image generation to complete
        try:
            logger.debug("Waiting for image generation to complete...")
            global_request_queue.join()
            workload['thread'].join(timeout=10.0)  # Add a timeout to prevent hanging
            logger.debug("Queue processing completed")
        except Exception as e:
            logger.error(f"Error waiting for image generation: {str(e)}")
            
        # Try both paths again after generation
        paths_to_check = [file_path, alt_file_path]
        for check_path in paths_to_check:
            if os.path.exists(check_path) and os.path.getsize(check_path) > 0:
                logger.info(f"Successfully generated image: {check_path}")
                return send_file(check_path)
                
        # If we get here, image generation failed
        logger.error(f"Failed to generate image at either path: {file_path} or {alt_file_path}")
        
        # Check source audio files
        audio_path = osfolder + os.sep.join(mod_path.split('/')[:-1])
        audio_path_alt = osfolder + os.sep.join(path.split('/')[:-1])
        
        # Check both possible audio paths
        audio_paths = [audio_path, audio_path_alt]
        audio_exists = False
        pickle_exists = False
        
        for check_audio_path in audio_paths:
            if os.path.exists(check_audio_path):
                audio_exists = True
                if os.path.exists(check_audio_path + '.pickle'):
                    pickle_exists = True
                    break
                    
        if not audio_exists:
            return create_error_image(f"Audio file not found. Tried:\n{audio_path}\n{audio_path_alt}")
        if not pickle_exists:
            return create_error_image(f"Metadata file not found. Tried:\n{audio_path}.pickle\n{audio_path_alt}.pickle")
                
        # Try to list the temp directory to help with debugging
        try:
            import tempfile
            temp_dir = os.path.join(tempfile.gettempdir(), "battykoda_temp")
            if os.path.exists(temp_dir):
                temp_contents = os.listdir(temp_dir)
                logger.debug(f"Temp directory {temp_dir} contents: {temp_contents}")
        except Exception as temp_e:
            logger.error(f"Error listing temp directory: {str(temp_e)}")
            
        # General error message
        return create_error_image(f"Failed to generate image. Please check the server logs.")
            
    except Exception as e:
        logger.error(f"Error in handle_image: {str(e)}")
        logger.debug(traceback.format_exc())
        # Return error placeholder
        return send_file('static/broken_image.png')

def create_error_image(error_message):
    """
    Create an error image with a custom message.
    
    Args:
        error_message: The error message to display
        
    Returns:
        Flask response with the error image
    """
    try:
        import io
        from PIL import Image, ImageDraw, ImageFont
        
        # Create a blank image with text
        img = Image.new('RGB', (500, 300), color=(255, 0, 0))
        d = ImageDraw.Draw(img)
        
        # Split long error messages into multiple lines
        message_lines = []
        words = error_message.split()
        current_line = []
        
        for word in words:
            current_line.append(word)
            if len(' '.join(current_line)) > 50:  # 50 chars max per line
                message_lines.append(' '.join(current_line[:-1]))
                current_line = [word]
        
        if current_line:
            message_lines.append(' '.join(current_line))
            
        # Draw each line of text
        for i, line in enumerate(message_lines):
            d.text((10, 10 + (i * 20)), line, fill=(255, 255, 255))
            
        # Convert to bytes
        img_io = io.BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        
        return send_file(img_io, mimetype='image/png')
    except Exception as e:
        logger.error(f"Error creating error image: {str(e)}")
        return send_file('static/broken_image.png')


@app.route('/audio/<path:path>')
@login_required
def handle_sound(path):
    # Convert path to OS-specific format
    mod_path = utils.convert_path_to_os_specific(path)
    
    slowdown = 5
    if not exists(appropriate_file(path, request.args, osfolder)):
        SoftCreateFolders.soft_create_folders(appropriate_file(path, request.args, osfolder, folder_only=True))
        call_to_do = int(request.args['call'])
        overview = request.args['overview'] == 'True'
        hwin = Hwin.overview_hwin if overview else Hwin.normal_hwin
        
        # Use the modified path with correct home directory
        audio_path = osfolder + os.sep.join(mod_path.split('/')[:-1])
        thr_x1, fs, hashof = GetAudioBit.get_audio_bit(audio_path, call_to_do, hwin)
        
        thr_x1 = thr_x1[:, int(request.args['channel'])]
        assert request.args['hash'] == hashof
        scipy.io.wavfile.write(appropriate_file(path, request.args, osfolder),
                               fs // slowdown,
                               thr_x1.astype('float32').repeat(slowdown) * float(request.args['loudness']))

    return send_file(appropriate_file(path, request.args, osfolder))


@app.route('/species_info/<species_name>')
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
    
    # Get current username for project creation links and list all users
    import getpass
    import os
    current_user = getpass.getuser()
    
    # Get all user directories from the system
    other_users = []
    try:
        if platform.system() == "Darwin":  # macOS
            user_dir = "/Users"
            users = os.listdir(user_dir)
            # Filter out system directories and dotfiles
            other_users = [u for u in users if not u.startswith('.') and u != 'Shared' and u != current_user]
            other_users.sort()
    except:
        pass
    
    content += f"""
            <p>Click below to navigate to this species template in your user directory:</p>
            <p><a href="/battycoda/home/{current_user}/{species_name}/" class="button" style="display: inline-block; padding: 12px 20px; background-color: #2ecc71; color: white; text-decoration: none; border-radius: 5px; font-weight: bold; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">Open in Your Directory ({current_user})</a></p>
    """
    
    if other_users:
        content += """
            <p style="margin-top: 20px;">Or open in another user directory:</p>
            <div style="display: flex; flex-wrap: wrap; gap: 10px;">
        """
        
        for user in other_users:
            content += f"""
                <a href="/battycoda/home/{user}/{species_name}/" style="display: inline-block; padding: 8px 15px; background-color: #3498db; color: white; text-decoration: none; border-radius: 5px; margin-bottom: 10px;">{user}</a>
            """
            
        content += """
            </div>
        """
    
    content += """
        </div>
        
        <div style="margin-top: 30px; text-align: center; border-top: 1px solid #eee; padding-top: 20px;">
            <a href="/" style="display: inline-block; padding: 10px 20px; background-color: #95a5a6; color: white; text-decoration: none; border-radius: 5px; margin-right: 10px;">Return to Home Page</a>
            <a href="/battycoda/home/" style="display: inline-block; padding: 10px 20px; background-color: #95a5a6; color: white; text-decoration: none; border-radius: 5px;">Browse All Users</a>
        </div>
    </div>
    """
    
    return render_template('listBC.html', data={'listicle': Markup(content)})


if __name__ == '__main__':
    mainfunction()
else:
    # When imported as a module (e.g., by dev_server.py),
    # initialize the app but don't start the server
    initialize_app()
