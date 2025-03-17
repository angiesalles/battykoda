import os
import sys
import logging
import threading
import queue
from flask import Flask, render_template, url_for
from markupsafe import Markup
from flask_login import LoginManager, current_user, login_required

# Import utility functions
import utils

# Import auth module and database models 
from auth import auth_bp
from database import db, User

# Import our route modules
from routes import spectrogram_routes, directory_routes, path_routes, audio_routes

# Import other necessary modules
import Workers

# Configure logging
# All application logs go to both stdout and server.log with timestamps
# Format: YYYY-MM-DD HH:MM:SS,mmm - logger_name - LEVEL - message
# Clear the log file on startup
log_file = 'server.log'
if os.path.exists(log_file):
    open(log_file, 'w').close()  # Clear the log file
    logger = logging.getLogger('battykoda')
    logger.info("Cleared previous log file")

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, mode='w')  # Use 'w' mode to overwrite the file
    ]
)
logger = logging.getLogger('battykoda')

# Create Flask application
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

# Default settings for non-authenticated users
default_user_setting = {
    'limit_confidence': '90',
    'user_name': "",
    'contrast': '4',
    'loudness': '0.5',
    'main': '1'
}

# Global user setting (retained for backward compatibility)
global_user_setting = default_user_setting.copy()

# Global queues for worker threads
global_request_queue = queue.PriorityQueue()
global_work_queue = queue.PriorityQueue()

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    return User.query.get(int(user_id))

# Simple template filter for basic image rendering
@app.template_filter('render_image')
def render_image_filter(img_path):
    """
    Simple filter to render an image tag
    
    Args:
        img_path: Path to the image
        
    Returns:
        Safe HTML with the image
    """
    html = f'<img src="{img_path}" class="responsive-image" alt="Spectrogram"/>'
    return Markup(html)

def initialize_app():
    """Initialize the app by starting worker threads and creating necessary directories"""
    # Check if database file exists
    db_path = os.path.join(os.getcwd(), 'battycoda.db')
    
    # Special case for Replit - ensure parent directories exist
    if os.environ.get('REPL_SLUG') or os.environ.get('REPL_ID'):
        logger.info("Running in Replit environment, ensuring directories exist...")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # If database doesn't exist, create it automatically
    if not os.path.exists(db_path):
        logger.info("Database file doesn't exist. Creating database from scratch...")
        try:
            import create_db
            create_db.create_database()
            logger.info("Initial database creation successful")
        except Exception as e:
            logger.error(f"Failed to create initial database: {str(e)}")
    
    # Try to verify the database
    try:
        # Check database with the main app context
        with app.app_context():
            user_count = User.query.count()
            logger.info(f"Database check: Users table exists with {user_count} users")
    except Exception as e:
        logger.error(f"Database verification failed after initialization: {str(e)}")
        
        # Last resort: recreate the database
        try:
            logger.warning("Recreating database as last resort...")
            if os.path.exists(db_path):
                os.remove(db_path)
                logger.info("Removed invalid database file")
            
            import create_db
            create_db.create_database()
            logger.info("Last-resort database creation completed")
            
            # Re-initialize the app with the database
            with app.app_context():
                db.create_all()
        except Exception as final_error:
            logger.error(f"Final database creation failed: {str(final_error)}")
            logger.error("Unable to initialize database automatically. The application will likely fail.")
    
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
    
    # Register global queues with the spectrogram routes
    from routes.spectrogram_utils import register_queues
    register_queues(global_request_queue, global_work_queue, global_user_setting)
    
    # Start worker threads
    threading.Thread(target=Workers.worker,
                     args=(global_request_queue, global_work_queue),
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

# Route definitions
# Main routes
@app.route('/')
def mainpage():
    """Main landing page"""
    return directory_routes.mainpage()

@app.route('/login')
def main_login():
    """Direct login route for compatibility with legacy logout"""
    return directory_routes.main_login()

@app.route('/logout')
def legacy_logout():
    """Legacy direct logout route for compatibility"""
    return directory_routes.legacy_logout()

@app.route('/home')
@login_required
def home():
    """Home page with user directories and species info"""
    return directory_routes.home()

@app.route('/back/<path:path>')
@login_required
def handle_back(path):
    """Handle back navigation (undo)"""
    return path_routes.handle_back(path)

@app.route('/<path:path>', methods=['POST', 'GET'])
@login_required
def handle_batty(path):
    """Main content handler for all paths"""
    return path_routes.handle_batty(path)

# Spectrogram and audio routes
@app.route('/spectrogram', methods=['GET'])
@login_required
def handle_spectrogram():
    """Handle spectrogram generation and serving"""
    return spectrogram_routes.handle_spectrogram()

@app.route('/audio/snippet', methods=['GET'])
@login_required
def handle_audio_snippet():
    """Handle audio snippet generation and serving"""
    return audio_routes.handle_audio_snippet()

@app.route('/species_info/<species_name>')
def species_info(species_name):
    """Display information about a specific species template"""
    return directory_routes.species_info(species_name)

@app.route('/debug/queue_status')
def debug_queue_status():
    """Debug endpoint to check queue registration status"""
    from routes.spectrogram_utils import get_queue_status
    import json
    status = get_queue_status()
    return json.dumps(status, default=str), 200, {'Content-Type': 'application/json'}

if __name__ == '__main__':
    mainfunction()
else:
    # When imported as a module (e.g., by dev_server.py),
    # initialize the app but don't start the server
    initialize_app()
