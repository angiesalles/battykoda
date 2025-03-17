"""
Debug utilities for BattyCoda application.
Provides auto-detection and connection to PyCharm debugger.
"""
import socket
import logging

# Set up logging
logger = logging.getLogger('battycoda.debug')

def try_connect_debugger(host='localhost', port=12345, timeout=0.5):
    """
    Attempt to connect to PyCharm debugger with auto-detection.
    Will try to connect to a debugger on the specified port if available,
    but gracefully continue if not available.
    
    Args:
        host (str): Hostname where debugger is running
        port (int): Port number for the debugger
        timeout (float): Connection timeout in seconds
    
    Returns:
        bool: True if successfully connected to debugger, False otherwise
    """
    # First check if debugger is available by attempting to connect to the port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    debugger_available = False
    
    try:
        # Try to connect to see if the port is open
        result = sock.connect_ex((host, port))
        debugger_available = (result == 0)
    except Exception:
        # If any error occurs, assume no debugger
        debugger_available = False
    finally:
        sock.close()
    
    if debugger_available:
        # Debugger seems to be available, try to connect
        try:
            import pydevd_pycharm
            # Connect to the PyCharm debugger
            logger.info(f"PyCharm debugger found on port {port}, attempting to connect...")
            print(f"PyCharm debugger found on port {port}, attempting to connect...")
            
            pydevd_pycharm.settrace(
                host, 
                port=port,
                stdoutToServer=True, 
                stderrToServer=True,
                suspend=False  # Don't pause execution
            )
            
            logger.info("✅ PyCharm debugger connected successfully")
            print("✅ PyCharm debugger connected successfully")
            return True
        except ImportError:
            logger.warning("⚠️ PyCharm debugger module not available - install 'pydevd-pycharm' package to enable debugging")
            print("⚠️ PyCharm debugger module not available - install 'pydevd-pycharm' package to enable debugging")
            return False
        except Exception as e:
            logger.warning(f"⚠️ PyCharm debugger connection failed: {str(e)}")
            print(f"⚠️ PyCharm debugger connection failed: {str(e)}")
            return False
    else:
        logger.debug(f"PyCharm debugger not detected on port {port} - continuing without debugging")
        print(f"PyCharm debugger not detected on port {port} - continuing without debugging")
        return False