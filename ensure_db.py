"""
Ensures the database is properly initialized for BattyCoda.
This script runs before the main application starts on Replit.
"""
import os
import sys
import logging
from flask import Flask
from database import db, User
from werkzeug.security import generate_password_hash
import sqlite3

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger('battycoda-db-init')

def ensure_db_initialized():
    """Make sure the database exists and has all required tables"""
    db_path = 'battycoda.db'
    app = Flask(__name__)
    
    # Configure the app
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'battycoda-secret-key-development')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize the database with the app
    db.init_app(app)
    
    with app.app_context():
        logger.info("Checking database and initializing if needed...")
        
        # Create all tables
        try:
            db.create_all()
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating database tables: {str(e)}")
            raise
        
        # Check if tables were actually created
        try:
            # Verify users table exists
            test_user = User.query.first()
            logger.info(f"Database check - Users table exists, found {User.query.count()} users")
        except Exception as e:
            if 'no such table' in str(e):
                logger.error("Users table not found, attempting repair...")
                # Try to create tables directly
                try:
                    # Direct SQLite verification and repair
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    
                    # Check if users table exists
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
                    if not cursor.fetchone():
                        logger.info("Recreating users table directly...")
                        # SQL for users table creation if needed
                        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT UNIQUE NOT NULL,
                            email TEXT UNIQUE NOT NULL,
                            password_hash TEXT NOT NULL,
                            is_admin BOOLEAN NOT NULL DEFAULT 0,
                            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            last_login TIMESTAMP,
                            reset_token TEXT,
                            reset_token_expiry TIMESTAMP,
                            login_code TEXT,
                            login_code_expiry TIMESTAMP,
                            default_contrast TEXT,
                            default_loudness TEXT,
                            default_main_channel TEXT,
                            default_confidence_threshold TEXT
                        )''')
                        conn.commit()
                        logger.info("Users table created directly via SQLite")
                    
                    conn.close()
                    
                    # Now try creating all tables again via SQLAlchemy
                    db.create_all()
                    logger.info("Database tables recreation completed")
                except Exception as repair_error:
                    logger.error(f"Database repair failed: {str(repair_error)}")
                    raise
            else:
                logger.error(f"Unknown database error: {str(e)}")
                raise
        
        # Create test users if they don't exist
        create_test_users(app)
        
        # Create required directories
        create_directories()
        
        logger.info("Database initialization complete")

def create_test_users(app):
    """Create test users for the application"""
    with app.app_context():
        # Create admin user if it doesn't exist
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            logger.info("Creating admin user...")
            admin = User(
                username='admin',
                email='admin@example.com',
                password_hash=generate_password_hash('admin123'),
                is_admin=True
            )
            db.session.add(admin)
            
            # Create a demo user as well
            demo = User(
                username='demo',
                email='demo@example.com',
                password_hash=generate_password_hash('demo123'),
                is_admin=True
            )
            db.session.add(demo)
            
            try:
                db.session.commit()
                logger.info("Test users created successfully")
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error creating test users: {str(e)}")
        else:
            logger.info("Test users already exist")

def create_directories():
    """Create necessary directories for the application"""
    required_dirs = [
        'data',
        'data/home',
        'static/tempdata'
    ]
    
    for directory in required_dirs:
        if not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
                logger.info(f"Created directory: {directory}")
            except Exception as e:
                logger.error(f"Error creating directory {directory}: {str(e)}")

if __name__ == "__main__":
    logger.info("Starting database initialization...")
    try:
        ensure_db_initialized()
        logger.info("Database initialization completed successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        sys.exit(1)