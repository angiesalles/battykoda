#!/usr/bin/env python3
"""
Single setup script for BattyCoda
Handles all setup tasks including database initialization, R setup, and launching the app
"""
import os
import sys
import subprocess
import time
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger('battycoda-setup')

def run_command(command, name, check=True):
    """Run a command and log output"""
    logger.info(f"Running {name}...")
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Stream output in real-time
        for line in process.stdout:
            line = line.strip()
            if line:
                logger.info(f"{name}: {line}")
        
        return_code = process.wait()
        
        if return_code == 0:
            logger.info(f"{name} completed successfully")
            return True
        else:
            logger.error(f"{name} failed with code {return_code}")
            return False
    except Exception as e:
        logger.error(f"Error running {name}: {str(e)}")
        return False

def setup_environment():
    """Set up environment variables"""
    logger.info("Setting up environment variables...")
    
    # Set environment variables
    os.environ['FLASK_DEBUG'] = os.environ.get('FLASK_DEBUG', '1') 
    os.environ['PYTHON_VERSION'] = os.environ.get('PYTHON_VERSION', '3.12')
    
    # Special setup for R libraries in Replit
    if os.environ.get('REPL_SLUG') or os.environ.get('REPL_ID'):
        logger.info("Running in Replit environment")
        # Set R library path in the current directory for Replit
        os.environ['R_LIBS_USER'] = os.path.join(os.getcwd(), '.r_libs')
    else:
        # For local development, use user's home directory
        os.environ['R_LIBS_USER'] = os.path.expanduser('~/.r_libs')
    
    # Create R_LIBS_USER directory
    r_libs_dir = os.environ.get('R_LIBS_USER')
    logger.info(f"Creating R libraries directory at: {r_libs_dir}")
    os.makedirs(r_libs_dir, exist_ok=True)
    
    # Create other required directories
    logger.info("Creating required application directories")
    os.makedirs('data/home', exist_ok=True)
    os.makedirs('static/tempdata', exist_ok=True)
    
    return True

def install_python_requirements():
    """Install required Python packages"""
    logger.info("Installing Python requirements...")
    return run_command(
        ['pip', 'install', '-r', 'requirements.txt'],
        'pip install'
    )

def initialize_database():
    """Initialize the database directly"""
    logger.info("Initializing database directly...")
    
    # First, check if database file exists, if so, delete it to start fresh
    db_path = os.path.join(os.getcwd(), 'battycoda.db')
    logger.info(f"Using database at path: {db_path}")
    
    if os.path.exists(db_path):
        logger.info(f"Removing existing database at {db_path}")
        try:
            os.remove(db_path)
            logger.info("Removed old database file")
        except Exception as e:
            logger.error(f"Error removing database: {str(e)}")
    
    # Import necessary modules
    try:
        logger.info("Importing database modules...")
        from flask import Flask
        from database import db, User
        from werkzeug.security import generate_password_hash
        import sqlite3
        
        # Create a Flask app
        app = Flask(__name__)
        
        # Configure the app
        app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'battycoda-secret-key-development')
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        # Initialize the database with the app
        db.init_app(app)
        
        # Create all tables
        with app.app_context():
            logger.info("Creating database tables...")
            db.create_all()
            
            # Verify tables
            try:
                count = User.query.count()
                logger.info(f"Users table exists with {count} users")
            except Exception as e:
                logger.error(f"Error verifying users table: {str(e)}")
                raise
            
            # Create admin user
            logger.info("Creating admin user...")
            admin = User(
                username='admin',
                email='admin@example.com',
                password_hash=generate_password_hash('admin123'),
                is_admin=True
            )
            db.session.add(admin)
            
            # Create demo user
            logger.info("Creating demo user...")
            demo = User(
                username='demo',
                email='demo@example.com',
                password_hash=generate_password_hash('demo123'),
                is_admin=True
            )
            db.session.add(demo)
            
            # Commit changes
            try:
                db.session.commit()
                logger.info("Users created successfully")
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error creating users: {str(e)}")
                raise
            
            # Verify again
            count = User.query.count()
            logger.info(f"Database now has {count} users")
        
        logger.info("Database initialization completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        # Fall back to using ensure_db.py
        logger.info("Trying ensure_db.py as fallback...")
        return run_command(
            ['python', 'ensure_db.py'],
            'Database initialization (fallback)'
        )

def setup_r_environment():
    """Set up R environment if R is available"""
    # First check if R is installed
    try:
        r_check = subprocess.run(
            ['which', 'R'],
            capture_output=True,
            text=True,
            check=False
        )
        
        if r_check.returncode == 0:
            logger.info("R is installed, setting up R environment...")
            
            # Check if we're on Replit
            if os.environ.get('REPL_SLUG') or os.environ.get('REPL_ID'):
                logger.info("Running R setup for Replit environment...")
                
                # First run the R package installation script
                run_command(
                    ['Rscript', 'install_r_packages.R'],
                    'Install R packages',
                    check=False
                )
                
                # Then run the setup script for warbler
                run_command(
                    ['Rscript', 'setup_warbler.R'],
                    'Setup warbleR package',
                    check=False
                )
                
                # Check if model file exists
                if not os.path.exists('static/mymodel.RData'):
                    logger.warning("Model file not found at static/mymodel.RData")
                    logger.warning("Bat call classification may not work correctly")
                else:
                    logger.info("Model file found at static/mymodel.RData")
                
                return True
            else:
                # Use the check_r_setup.py script for non-Replit environments
                return run_command(
                    ['python', 'check_r_setup.py'],
                    'R setup',
                    check=False  # Don't fail if R setup fails
                )
        else:
            logger.warning("R is not installed, skipping R setup")
            logger.warning("Bat call classification will not work without R")
            return True  # Continue anyway
    except Exception as e:
        logger.warning(f"Error checking for R: {str(e)}")
        return True  # Continue anyway

def start_application():
    """Start the main application"""
    logger.info("Starting BattyCoda application...")
    
    # Use os.execv to replace the current process with the main.py script
    # This ensures the application runs in the foreground and Replit can see the output
    os.execv(sys.executable, [sys.executable, 'main.py'])
    
    # This code will never be reached because execv replaces the current process

def main():
    """Main setup function"""
    logger.info("Starting BattyCoda setup...")
    
    # Run setup steps
    setup_environment()
    install_python_requirements()
    initialize_database()
    setup_r_environment()
    
    # Start the application
    start_application()

if __name__ == "__main__":
    main()