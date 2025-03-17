"""
Utility functions for spectrogram processing.
"""
import os
import io
import logging
from PIL import Image, ImageDraw

# Configure logging
logger = logging.getLogger('battykoda.spectrogram_utils')

def create_error_image(error_message):
    """
    Create an error image with a custom message.
    
    Args:
        error_message: The error message to display
        
    Returns:
        Flask response with the error image
    """
    try:
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
        
        from flask import send_file
        return send_file(img_io, mimetype='image/png')
    except Exception as e:
        logger.error(f"Error creating error image: {str(e)}")
        return "", 404


# Global queues from main app
global_request_queue = None
global_work_queue = None
global_user_setting = None


def register_queues(request_queue, work_queue, user_setting):
    """
    Register global queues from main app.
    
    Args:
        request_queue: The global request queue
        work_queue: The global work queue
        user_setting: The global user settings
    """
    global global_request_queue, global_work_queue, global_user_setting
    global_request_queue = request_queue
    global_work_queue = work_queue
    global_user_setting = user_setting
    
    # Log registration
    logger.info("Queues registered in spectrogram_utils:")
    logger.info(f"  - Request queue: {request_queue is not None}")
    logger.info(f"  - Work queue: {work_queue is not None}")
    logger.info(f"  - User setting: {user_setting}")
    
def get_queue_status():
    """
    Get the current status of global queues for debugging.
    
    Returns:
        dict: Status of global queues and settings
    """
    return {
        'request_queue_initialized': global_request_queue is not None,
        'work_queue_initialized': global_work_queue is not None,
        'user_setting': global_user_setting
    }