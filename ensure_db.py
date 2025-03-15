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

def verify_database_file(db_path):
    """Verify that the database file exists and is a valid SQLite database"""
    if os.path.exists(db_path):
        logger.info(f"Database file exists at {db_path}")
        try:
            # Try to open the database and verify schema
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check if it has a users table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if cursor.fetchone():
                logger.info("Existing database has users table")
                
                # Check schema of users table
                cursor.execute("PRAGMA table_info(users)")
                columns = cursor.fetchall()
                expected_columns = ["id", "username", "email", "password_hash", "is_admin"]
                
                column_names = [col[1] for col in columns]
                missing_columns = [col for col in expected_columns if col not in column_names]
                
                if missing_columns:
                    logger.warning(f"Users table is missing columns: {missing_columns}")
                    logger.warning("The database schema is incomplete. Will recreate database.")
                    conn.close()
                    return False
                else:
                    logger.info("Users table schema is valid")
                    conn.close()
                    return True
            else:
                logger.warning("Database file exists but has no users table")
                conn.close()
                return False
        except sqlite3.Error as e:
            logger.error(f"Error verifying database: {str(e)}")
            return False
    else:
        logger.info(f"Database file doesn't exist at {db_path}")
        return False

def ensure_db_initialized():
    """Make sure the database exists and has all required tables"""
    # Use absolute path for the database to ensure consistency
    db_path = os.path.join(os.getcwd(), 'battycoda.db')
    logger.info(f"Using database at path: {db_path}")
    
    # Ensure parent directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # Check if existing database is valid
    if not verify_database_file(db_path):
        logger.warning("Removing invalid database file")
        try:
            if os.path.exists(db_path):
                os.remove(db_path)
                logger.info("Removed invalid database file")
        except Exception as e:
            logger.error(f"Error removing database file: {str(e)}")
    
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
                        # First, drop the table if it exists but is malformed
                        logger.info("Dropping users table if it exists but is incomplete...")
                        cursor.execute("DROP TABLE IF EXISTS users")
                        
                        # Create the users table with proper schema
                        logger.info("Creating users table with correct schema...")
                        cursor.execute('''CREATE TABLE users (
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
                    
                    # Verify tables again
                    try:
                        count = User.query.count()
                        logger.info(f"Verification successful: Users table exists with {count} users")
                    except Exception as verify_error:
                        logger.error(f"Verification failed after recreation: {str(verify_error)}")
                        raise
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