"""
Debug utilities for BattyCoda application.
Provides auto-detection and connection to PyCharm debugger.
"""
import socket
import logging

# Set up logging
logger = logging.getLogger('battycoda.debug')

def try_connect_debugger(host='localhost', port=12345, timeout=0.5, alternative_hosts=None):
    """
    Attempt to connect to PyCharm debugger with auto-detection.
    Will try to connect to a debugger on the specified port if available,
    but gracefully continue if not available.
    
    Args:
        host (str): Primary hostname where debugger is running
        port (int): Port number for the debugger
        timeout (float): Connection timeout in seconds
        alternative_hosts (list): Optional list of alternative hostnames to try
    
    Returns:
        bool: True if successfully connected to debugger, False otherwise
    """
    # Set default alternative hosts if none provided
    if alternative_hosts is None:
        # Try these hosts in order if the primary host fails
        # Include the EC2 instance's private IP address
        alternative_hosts = ['host.docker.internal', '127.0.0.1', '172.17.0.1', '172.31.23.171']
    
    # Print connection attempt info 
    print(f"🔍 Checking for PyCharm debugger on port {port}...")
    print(f"  Primary host: {host}")
    print(f"  Alternative hosts: {alternative_hosts}")
    
    # Try primary host first
    hosts_to_try = [host] + alternative_hosts
    connected_host = None
    
    # Try each host until we find one that connects
    for current_host in hosts_to_try:
        # First check if debugger is available by attempting to connect to the port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        debugger_available = False
        
        try:
            # Try to connect to see if the port is open
            print(f"  Trying {current_host}:{port}...")
            result = sock.connect_ex((current_host, port))
            
            if result == 0:
                debugger_available = True
                connected_host = current_host
                print(f"  ✅ Port {port} is open on {current_host}")
            else:
                print(f"  ❌ Port {port} is closed on {current_host} (error code: {result})")
                
        except Exception as e:
            # If any error occurs, assume no debugger
            print(f"  ❌ Error checking {current_host}:{port} - {str(e)}")
            debugger_available = False
        finally:
            sock.close()
        
        if debugger_available:
            break
    
    if debugger_available and connected_host:
        # Debugger seems to be available, try to connect
        try:
            import pydevd_pycharm
            # Connect to the PyCharm debugger
            logger.info(f"PyCharm debugger found on {connected_host}:{port}, attempting to connect...")
            print(f"🔌 PyCharm debugger found on {connected_host}:{port}, attempting to connect...")
            
            pydevd_pycharm.settrace(
                connected_host, 
                port=port,
                stdoutToServer=True, 
                stderrToServer=True,
                suspend=False  # Don't pause execution
            )
            
            logger.info(f"✅ PyCharm debugger connected successfully to {connected_host}:{port}")
            print(f"✅ PyCharm debugger connected successfully to {connected_host}:{port}")
            return True
        except ImportError:
            logger.warning("⚠️ PyCharm debugger module not available - install 'pydevd-pycharm' package to enable debugging")
            print("⚠️ PyCharm debugger module not available - install 'pydevd-pycharm' package to enable debugging")
            return False
        except Exception as e:
            logger.warning(f"⚠️ PyCharm debugger connection failed: {str(e)}")
            print(f"⚠️ PyCharm debugger connection failed: {str(e)}")
            print(f"   Full error: {repr(e)}")
            return False
    else:
        logger.debug(f"PyCharm debugger not detected on any host for port {port} - continuing without debugging")
        print(f"ℹ️ PyCharm debugger not detected on any host for port {port} - continuing without debugging")
        return False