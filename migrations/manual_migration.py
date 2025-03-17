from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os
import sys

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db

def run_migration():
    with app.app_context():
        # Check if the column already exists
        result = db.session.execute("PRAGMA table_info(user)").fetchall()
        columns = [row[1] for row in result]
        
        if 'wallet_address' not in columns:
            print("Adding wallet_address column to User table...")
            db.session.execute("ALTER TABLE user ADD COLUMN wallet_address VARCHAR(255)")
            db.session.commit()
            print("Migration completed successfully!")
        else:
            print("Column wallet_address already exists in User table.")

if __name__ == "__main__":
    run_migration()