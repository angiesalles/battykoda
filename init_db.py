"""
Initialize the database for BattyCoda.
This script creates all necessary tables and adds a demo user.
"""
from flask import Flask
from database import db, User
from werkzeug.security import generate_password_hash
import os

def init_db():
    """Initialize the database"""
    # Create a Flask app for database initialization
    app = Flask(__name__)
    
    # Configure the app
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'battycoda-secret-key-development')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///battycoda.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize the database with the app
    db.init_app(app)
    
    # Create the database schema
    print("Creating database tables...")
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Check if demo user exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print("Creating admin user...")
            admin = User(
                username='admin',
                email='admin@example.com',
                password_hash=generate_password_hash('admin123'),
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()
            print("Admin user created with username 'admin' and password 'admin123'")
        else:
            print("Admin user already exists")
        
        # Create a demo user for Replit
        demo = User.query.filter_by(username='demo').first()
        if not demo:
            print("Creating demo user for Replit...")
            demo = User(
                username='demo',
                email='demo@example.com',
                password_hash=generate_password_hash('demo123'),
                is_admin=True
            )
            db.session.add(demo)
            db.session.commit()
            print("Demo user created with username 'demo' and password 'demo123'")
        else:
            print("Demo user already exists")
            
        # Check if the tables were created properly
        users_count = User.query.count()
        print(f"Database initialized with {users_count} users")
    
    print("Database initialization complete")

if __name__ == "__main__":
    # Create instance directory if needed
    os.makedirs('instance', exist_ok=True)
    init_db()