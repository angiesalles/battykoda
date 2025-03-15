"""
Create the database from scratch for BattyCoda.
This script creates the database directly with SQLite.
"""
import os
import sqlite3
import datetime

def create_database():
    """Create the database tables directly with SQLite"""
    # Remove existing database if it exists
    if os.path.exists('battycoda.db'):
        os.remove('battycoda.db')
        print("Removed existing database")
    
    # Connect to the database
    conn = sqlite3.connect('battycoda.db')
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username VARCHAR(64) UNIQUE NOT NULL,
        email VARCHAR(120) UNIQUE NOT NULL,
        password_hash VARCHAR(128) NOT NULL,
        is_admin BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP,
        reset_token VARCHAR(100),
        reset_token_expiry TIMESTAMP,
        login_code VARCHAR(8),
        login_code_expiry TIMESTAMP,
        default_contrast FLOAT DEFAULT 0.5,
        default_loudness FLOAT DEFAULT 0.8,
        default_main_channel INTEGER DEFAULT 1,
        default_confidence_threshold FLOAT DEFAULT 70.0
    )
    ''')
    
    # Create an admin user
    from werkzeug.security import generate_password_hash
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
    INSERT INTO users (
        username, email, password_hash, is_admin, created_at, 
        default_contrast, default_loudness, default_main_channel, default_confidence_threshold
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        'admin', 'admin@example.com', generate_password_hash('admin123'), 
        True, now, 0.5, 0.8, 1, 70.0
    ))
    
    # Create indexes
    cursor.execute('CREATE INDEX idx_users_username ON users (username)')
    cursor.execute('CREATE INDEX idx_users_email ON users (email)')
    
    # Commit changes and close connection
    conn.commit()
    conn.close()
    
    print("Database created successfully with admin user (username: 'admin', password: 'admin123')")

if __name__ == '__main__':
    create_database()