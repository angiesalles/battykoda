"""
PyCharm debugger configuration for BattyCoda.

This module provides a function to activate the PyCharm debugger
with a single import.
"""
import sys
import os

def activate_debugger(port=12345):
    """
    Activates the PyCharm debugger.
    
    This function attempts to connect to a PyCharm debugging server running 
    on localhost at the specified port. If the connection fails, it will 
    continue execution without the debugger.
    
    Skip activation when running tests to avoid connection errors.
    
    Args:
        port (int): The port on which PyCharm is listening for debug connections.
    """
    # Skip debugger activation when running tests
    if 'test' in sys.argv:
        return
        
    try:
        import pydevd_pycharm
        pydevd_pycharm.settrace(
            'localhost', 
            port=port, 
            stdoutToServer=True, 
            stderrToServer=True
        )
        print(f"PyCharm debugger activated on port {port}")
    except ConnectionRefusedError:
        print(f"PyCharm debugger connection refused on port {port}. Running without debugger.")
    except Exception as e:
        print(f"Failed to activate PyCharm debugger: {e}")