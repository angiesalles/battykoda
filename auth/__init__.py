# Auth package
from flask import Blueprint

# Create a blueprint for authentication routes
auth_bp = Blueprint('auth', __name__)

# Import route modules to register them with the blueprint
from auth import basic_routes, account_routes