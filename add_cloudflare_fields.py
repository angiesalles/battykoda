"""
Migration script to add Cloudflare authentication fields to the database.
"""
import os
import sys
import logging
import sqlite3
from flask import Flask
from database import db

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_db_path():
    """Find the correct database path"""
    instance_db_path = os.path.join('instance', 'battycoda.db')
    root_db_path = 'battycoda.db'
    
    if os.path.exists(instance_db_path):
        return instance_db_path
    elif os.path.exists(root_db_path):
        return root_db_path
    else:
        logger.error("No database file found!")
        sys.exit(1)

def add_cloudflare_fields():
    """Add Cloudflare authentication fields to the users table"""
    db_path = check_db_path()
    logger.info(f"Using database at: {db_path}")
    
    # Connect to the database directly
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    
    # Add new columns if they don't exist
    try:
        if 'is_cloudflare_user' not in columns:
            logger.info("Adding is_cloudflare_user column...")
            cursor.execute("ALTER TABLE users ADD COLUMN is_cloudflare_user BOOLEAN DEFAULT 0")
            
        if 'cloudflare_user_id' not in columns:
            logger.info("Adding cloudflare_user_id column...")
            cursor.execute("ALTER TABLE users ADD COLUMN cloudflare_user_id VARCHAR(100)")
            
            # Create index for cloudflare_user_id
            logger.info("Creating index for cloudflare_user_id...")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_cloudflare_id ON users (cloudflare_user_id)")
            
        conn.commit()
        logger.info("Migration completed successfully.")
    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"SQLite error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_cloudflare_fields()