"""
Initialize the database for BattyCoda.
This script creates all necessary tables and adds an admin user.
"""
from main import app, db, User
from flask import Flask
import os

def init_db():
    """Initialize the database"""
    print("Creating database tables...")
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Check if admin user exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print("Creating admin user...")
            admin = User(
                username='admin',
                email='admin@example.com',
                is_admin=True
            )
            admin.password = 'admin123'  # Development password only
            db.session.add(admin)
            db.session.commit()
            print("Admin user created with username 'admin' and password 'admin123'")
        else:
            print("Admin user already exists")
            
        # Check if the tables were created properly
        users_count = User.query.count()
        print(f"Database initialized with {users_count} users")
    
    print("Database initialization complete")

if __name__ == "__main__":
    # The database is in the current directory
    db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    if db_path and '/' in db_path:  # Only create directories if needed
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    init_db()