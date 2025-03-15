#!/usr/bin/env python3
"""
Script to check if R and required packages are installed
and install them if necessary. Specifically designed for Replit.
"""
import os
import sys
import logging
import subprocess
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger('battycoda-r-setup')

def check_r_installed():
    """Check if R is installed and available"""
    try:
        result = subprocess.run(
            ["which", "R"],
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Error checking for R: {str(e)}")
        return False

def check_warbler_installed():
    """Check if warbleR package is installed in R"""
    r_check_script = """
    if (requireNamespace("warbleR", quietly = TRUE)) {
        cat("warbleR is installed\\n")
        q(status = 0)
    } else {
        cat("warbleR is NOT installed\\n")
        q(status = 1)
    }
    """
    
    try:
        result = subprocess.run(
            ["R", "--vanilla", "-e", r_check_script],
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Error checking for warbleR: {str(e)}")
        return False

def install_warbler():
    """Run the setup_warbler.R script to install warbleR and dependencies"""
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "setup_warbler.R")
    
    if not os.path.exists(script_path):
        logger.error(f"Setup script not found at {script_path}")
        return False
    
    logger.info("Installing warbleR and dependencies... (this may take a while)")
    
    try:
        # Make the script executable
        os.chmod(script_path, 0o755)
        
        # Run the installation script
        process = subprocess.Popen(
            ["Rscript", "--vanilla", script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Stream the output in real-time
        for line in process.stdout:
            line = line.strip()
            if line:
                logger.info(f"R: {line}")
        
        # Wait for process to complete
        return_code = process.wait()
        
        if return_code == 0:
            logger.info("warbleR installation completed successfully")
            return True
        else:
            logger.error(f"warbleR installation failed with code {return_code}")
            return False
    except Exception as e:
        logger.error(f"Error installing warbleR: {str(e)}")
        return False

def test_warbler():
    """Run a simple test to ensure warbleR is working properly"""
    r_test_script = """
    tryCatch({
        library(warbleR)
        cat("warbleR loaded successfully\\n")
        # Try a simple function from warbleR
        x <- selection_table(data.frame(sound.files="test.wav", selec=1, start=0, end=1))
        cat("warbleR test passed!\\n")
        q(status = 0)
    }, error = function(e) {
        cat(sprintf("Error testing warbleR: %s\\n", e$message))
        q(status = 1)
    })
    """
    
    try:
        result = subprocess.run(
            ["R", "--vanilla", "-e", r_test_script],
            capture_output=True,
            text=True,
            check=False
        )
        
        # Log the output
        if result.stdout:
            for line in result.stdout.splitlines():
                logger.info(f"R test: {line}")
        
        if result.stderr:
            for line in result.stderr.splitlines():
                logger.error(f"R test error: {line}")
                
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Error testing warbleR: {str(e)}")
        return False

def main():
    """Main entry point for R package setup"""
    logger.info("Checking R environment for BattyCoda...")
    
    # Check if running on Replit
    is_replit = os.environ.get('REPL_ID') is not None
    if is_replit:
        logger.info("Running on Replit environment")
        
        # Create R_LIBS_USER directory if it doesn't exist
        r_libs_user = os.environ.get('R_LIBS_USER', '.r_libs')
        if not os.path.exists(r_libs_user):
            logger.info(f"Creating R package directory: {r_libs_user}")
            os.makedirs(r_libs_user, exist_ok=True)
    
    # Check if R is installed
    if not check_r_installed():
        logger.error("R is not installed or not in PATH")
        sys.exit(1)
    
    logger.info("R is installed")
    
    # Check if warbleR is already installed
    if check_warbler_installed():
        logger.info("warbleR is already installed")
        warbler_ok = test_warbler()
        if warbler_ok:
            logger.info("warbleR is working correctly")
            sys.exit(0)
        else:
            logger.warning("warbleR is installed but not functioning correctly")
    
    # We need to install warbleR
    logger.info("warbleR needs to be installed")
    
    # Install warbleR
    install_success = install_warbler()
    
    if install_success:
        # Test again after installation
        if test_warbler():
            logger.info("warbleR is now installed and working correctly")
            sys.exit(0)
        else:
            logger.error("warbleR installation completed but package is not functioning correctly")
            sys.exit(1)
    else:
        logger.error("Failed to install warbleR")
        sys.exit(1)

if __name__ == "__main__":
    main()