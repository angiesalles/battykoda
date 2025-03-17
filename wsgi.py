"""WSGI entry point for production servers like Gunicorn"""

# Try to connect to PyCharm debugger before importing the app
import utils
utils.try_connect_debugger()

# Now import the application
from main import app as application

if __name__ == "__main__":
    application.run()