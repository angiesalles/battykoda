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
    os.environ['FLASK_DEBUG'] = '1'
    os.environ['PYTHON_VERSION'] = '3.12'
    os.environ['R_LIBS_USER'] = '.r_libs'
    
    # Create R_LIBS_USER directory
    r_libs_dir = os.environ.get('R_LIBS_USER', '.r_libs')
    os.makedirs(r_libs_dir, exist_ok=True)
    
    # Create required directories
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
    """Initialize the database"""
    logger.info("Initializing database...")
    return run_command(
        ['python', 'ensure_db.py'],
        'Database initialization'
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
            return run_command(
                ['python', 'check_r_setup.py'],
                'R setup',
                check=False  # Don't fail if R setup fails
            )
        else:
            logger.warning("R is not installed, skipping R setup")
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