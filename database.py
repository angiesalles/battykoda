"""
Database setup and models for BattyCoda application.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
import os

# Initialize SQLAlchemy
db = SQLAlchemy()

# Define database path based on environment
def get_db_path():
    """Return the appropriate database URI based on environment"""
    # Try data volume first (should be writable)
    if os.path.exists('/app/data'):
        return 'sqlite:////app/data/battycoda.db'
    # Fall back to instance folder
    return 'sqlite:///instance/battycoda.db'

# Function to check if we're in testing mode
def is_testing():
    return os.environ.get('TESTING', 'False').lower() == 'true'

class User(UserMixin, db.Model):
    """User model for authentication and profile information."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True)
    email = db.Column(db.String(120), unique=True, index=True)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Authentication source
    is_cloudflare_user = db.Column(db.Boolean, default=False)
    cloudflare_user_id = db.Column(db.String(100), nullable=True, index=True)
    
    # Password reset fields
    reset_token = db.Column(db.String(100), nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)
    
    # One-time login code fields
    login_code = db.Column(db.String(8), nullable=True)
    login_code_expiry = db.Column(db.DateTime, nullable=True)
    
    # User preferences/settings
    default_contrast = db.Column(db.Float, default=0.5)
    default_loudness = db.Column(db.Float, default=0.8)
    default_main_channel = db.Column(db.Integer, default=1)
    default_confidence_threshold = db.Column(db.Float, default=70.0)
    
    @property
    def password(self):
        """Prevent password from being accessed directly"""
        raise AttributeError('password is not a readable attribute')
    
    @password.setter
    def password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def verify_password(self, password):
        """Verify the stored password against the provided password"""
        return check_password_hash(self.password_hash, password)
    
    def update_last_login(self):
        """Update the last login timestamp"""
        self.last_login = datetime.datetime.utcnow()
        db.session.commit()
    
    def get_settings_dict(self):
        """Return user settings as a dictionary for the templates"""
        return {
            'user_name': self.username,
            'contrast': self.default_contrast,
            'loudness': self.default_loudness,
            'main': self.default_main_channel,
            'limit_confidence': self.default_confidence_threshold
        }
    
    def __repr__(self):
        return f'<User {self.username}>'