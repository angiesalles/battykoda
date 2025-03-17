import os
import sys
import logging
import threading
import queue
from flask import Flask, render_template, url_for, request
from markupsafe import Markup
from flask_login import LoginManager, current_user, login_required

# Import utility functions - this needs to be before other imports
import utils

# Always try to connect to PyCharm debugger at startup
utils.try_connect_debugger()

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
# Use data volume for better permissions
if os.path.exists('/app/data'):
    db_path = '/app/data/battycoda.db'
else:
    db_path = os.path.join(os.getcwd(), 'battycoda.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
logger.info(f"Using database at: {db_path}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Cloudflare Access configuration
app.config['CLOUDFLARE_ACCESS_ENABLED'] = os.environ.get('CLOUDFLARE_ACCESS_ENABLED', 'False').lower() == 'true'
app.config['CLOUDFLARE_AUDIENCE'] = os.environ.get('CLOUDFLARE_AUDIENCE', '')

# Configure Celery integration
app.config.update(
    CELERY_BROKER_URL=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    CELERY_RESULT_BACKEND=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
)

# Initialize Celery with the app
from celery_app import make_celery
celery = make_celery(app)

# Initialize SQLAlchemy with the app
db.init_app(app)

# Initialize LoginManager
login_manager = LoginManager()
login_manager.login_view = 'auth.login'  # Flask-Login knows to prepend the blueprint URL prefix
login_manager.init_app(app)

# Import Cloudflare verification
from auth.cloudflare_verify import require_cloudflare, require_cloudflare_access

# Register auth blueprint
app.register_blueprint(auth_bp, url_prefix='/auth')

# Cloudflare verification middleware
@app.before_request
def verify_cloudflare_request():
    # Skip for development environment unless explicitly enabled
    if app.config.get('FLASK_ENV') == 'development' and not os.environ.get('ENFORCE_CLOUDFLARE_IN_DEV'):
        return None
    
    # Skip for local health check endpoints
    if request.path in ['/health', '/ping']:
        return None
    
    # Skip verification if Cloudflare is not enabled
    if not os.environ.get('CLOUDFLARE_ACCESS_ENABLED') == 'True':
        return None
    
    # Verify Cloudflare headers are present
    cf_connecting_ip = request.headers.get('CF-Connecting-IP')
    cf_ray = request.headers.get('CF-Ray')
    
    # If these headers aren't present, connection is likely not from Cloudflare
    if not cf_connecting_ip or not cf_ray:
        app.logger.warning(f"Blocking direct access attempt from {request.remote_addr}")
        return "Direct access to this server is not allowed", 403

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

# Custom login_required that accounts for Cloudflare Access
@app.before_request
def check_cloudflare_auth():
    """
    Check if the user is authenticated through Cloudflare Access and set up the user
    session accordingly for Flask-Login if needed.
    """
    # Skip for endpoints that don't require authentication
    if request.endpoint in ['static', 'health_check', 'cloudflare_test'] or \
       request.path.startswith('/static/') or \
       request.path in ['/health', '/ping', '/'] or \
       request.blueprint == 'auth':
        return None
    
    # Check if the user is already logged in through Flask-Login
    from flask_login import current_user
    if current_user.is_authenticated:
        return None
    
    # Allow a bypass for development and debugging
    if os.environ.get('CLOUDFLARE_BYPASS', 'False').lower() == 'true':
        app.logger.warning("⚠️ Cloudflare authentication bypass is enabled - this should not be used in production!")
        if request.args.get('admin_bypass') == 'true':
            # Auto-login as admin for testing
            user = User.query.filter_by(username='admin').first()
            if user:
                from flask_login import login_user
                login_user(user)
                app.logger.warning(f"⚠️ Auto-login as {user.username} via bypass")
                return None
            
    # If Cloudflare Access is enabled, check for Cloudflare authentication
    if os.environ.get('CLOUDFLARE_ACCESS_ENABLED') == 'True':
        # Import here to avoid circular imports
        from auth.cloudflare_verify import verify_cloudflare_jwt
        
        try:
            # Verify JWT token
            jwt_payload = verify_cloudflare_jwt()
            if jwt_payload:
                # Get user email from JWT
                email = jwt_payload.get('email')
                if email:
                    # Find or create user by email
                    user = User.query.filter_by(email=email).first()
                    if not user:
                        # Create a new user account for this Cloudflare user
                        from auth.utils import create_user_account
                        username = email.split('@')[0].replace('.', '_')  # Simple username from email
                        success, _, user = create_user_account(
                            username=username, 
                            email=email, 
                            is_cloudflare_user=True
                        )
                        if not success or not user:
                            app.logger.error(f"Failed to create user account for Cloudflare user: {email}")
                            return "Failed to create user account", 500
                    
                    # Update Cloudflare user information
                    if not user.is_cloudflare_user:
                        user.is_cloudflare_user = True
                        user.cloudflare_user_id = jwt_payload.get('sub')
                        db.session.commit()
                    
                    # Log the user in with Flask-Login
                    from flask_login import login_user
                    login_user(user)
                    
                    # Store Cloudflare user info for this request
                    g.cf_user = email
                    g.cf_user_id = jwt_payload.get('sub')
                    g.cf_user_data = jwt_payload
                    
                    app.logger.info(f"✅ Successful Cloudflare authentication for: {email}")
                    return None
        except Exception as e:
            app.logger.error(f"Error during Cloudflare authentication: {str(e)}")
            
            # If we're in production with Cloudflare Access required, don't fall through to normal auth
            if os.environ.get('ENFORCE_CLOUDFLARE_STRICT', 'False').lower() == 'true':
                return "Cloudflare Access authentication required", 401

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
# Health check endpoint (accessible directly for monitoring)
@app.route('/health')
def health_check():
    return {"status": "ok", "version": "1.0"}

# Cloudflare test route
@app.route('/cloudflare-test')
def cloudflare_test():
    # Import here to avoid circular imports
    from auth.utils import cloudflare_access_required
    from flask import current_app, g, jsonify
    from flask_login import current_user
    
    # Check if Cloudflare Access is enabled
    enabled = current_app.config.get('CLOUDFLARE_ACCESS_ENABLED', False)
    audience = current_app.config.get('CLOUDFLARE_AUDIENCE', '')
    bypass_enabled = os.environ.get('CLOUDFLARE_BYPASS', 'False').lower() == 'true'
    strict_mode = os.environ.get('ENFORCE_CLOUDFLARE_STRICT', 'False').lower() == 'true'
    
    # Get all possible Cloudflare headers and cookies for debugging
    cf_headers = {key: value for key, value in request.headers.items() if key.lower().startswith('cf-')}
    
    cf_cookies = {
        'CF_Authorization': request.cookies.get('CF_Authorization')
    }
    
    # Check certificate fetch status
    cert_status = None
    try:
        from auth.cloudflare_verify import get_cloudflare_certs
        certs = get_cloudflare_certs(audience)
        if certs:
            cert_status = {
                'success': True,
                'keys_count': len(certs.get('keys', [])),
                'certs_source': 'cached' if hasattr(get_cloudflare_certs, '_cf_certs_last_updated') else 'fresh'
            }
        else:
            cert_status = {
                'success': False,
                'message': 'Failed to fetch certificates'
            }
    except Exception as e:
        cert_status = {
            'success': False,
            'error': str(e)
        }
    
    # Check token validation if available
    token_validation = None
    if cf_headers.get('CF-Access-Jwt-Assertion') or cf_cookies.get('CF_Authorization'):
        try:
            from auth.cloudflare_verify import verify_cloudflare_jwt
            jwt_payload = verify_cloudflare_jwt()
            token_validation = {
                'valid': jwt_payload is not None,
                'user_info': jwt_payload if jwt_payload else 'Token validation failed'
            }
        except Exception as e:
            token_validation = {
                'valid': False,
                'error': str(e)
            }
    
    # Get user information
    cf_user = getattr(g, 'cf_user', None)
    flask_user = {
        'is_authenticated': current_user.is_authenticated,
        'username': current_user.username if current_user.is_authenticated else None,
        'email': current_user.email if current_user.is_authenticated else None,
        'is_cloudflare_user': current_user.is_cloudflare_user if current_user.is_authenticated else None
    }
    
    # Get environment information
    env_info = {
        'CLOUDFLARE_ACCESS_ENABLED': os.environ.get('CLOUDFLARE_ACCESS_ENABLED'),
        'CLOUDFLARE_AUDIENCE': os.environ.get('CLOUDFLARE_AUDIENCE'),
        'CLOUDFLARE_DOMAIN': os.environ.get('CLOUDFLARE_DOMAIN'),
        'CLOUDFLARE_BYPASS': os.environ.get('CLOUDFLARE_BYPASS'),
        'ENFORCE_CLOUDFLARE_STRICT': os.environ.get('ENFORCE_CLOUDFLARE_STRICT'),
        'FLASK_ENV': os.environ.get('FLASK_ENV')
    }
    
    return jsonify({
        "status": "ok" if enabled else "warning", 
        "message": "Cloudflare Access is enabled" if enabled else "Cloudflare Access is currently disabled",
        "audience": audience,
        "bypass_mode": bypass_enabled,
        "strict_mode": strict_mode,
        "cf_user": cf_user,
        "flask_user": flask_user,
        "cf_headers": cf_headers,
        "cf_cookies": cf_cookies,
        "cert_status": cert_status,
        "token_validation": token_validation,
        "env_info": env_info,
        "help": "Add ?admin_bypass=true to URL to bypass Cloudflare auth if CLOUDFLARE_BYPASS=True"
    })

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
    
@app.route('/status/task/<task_id>')
@login_required
def task_status(task_id):
    """Check the status of a celery task"""
    return spectrogram_routes.task_status(task_id)

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

@app.route('/debug/celery_status')
def debug_celery_status():
    """Debug endpoint to check Celery status"""
    from celery.task.control import inspect
    from tasks import celery
    import json
    
    try:
        i = inspect()
        status = {
            'active': i.active(),
            'scheduled': i.scheduled(),
            'reserved': i.reserved(),
            'revoked': i.revoked(),
            'registered': list(i.registered().keys()) if i.registered() else [],
            'stats': i.stats(),
            'broker': celery.conf.get('broker_url'),
        }
    except Exception as e:
        status = {'error': str(e)}
        
    return json.dumps(status, default=str), 200, {'Content-Type': 'application/json'}

if __name__ == '__main__':
    mainfunction()
else:
    # When imported as a module (e.g., by dev_server.py),
    # initialize the app but don't start the server
    initialize_app()
