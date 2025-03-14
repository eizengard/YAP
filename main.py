from dotenv import load_dotenv
import os
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Debug database URL
logger.debug(f"DATABASE_URL: {os.environ.get('DATABASE_URL')}")

# Ensure instance directory exists
db_path = os.environ.get("DATABASE_URL", "")
if db_path.startswith('sqlite:////'):
    # Absolute path
    file_path = db_path.replace('sqlite:////', '')
    db_dir = os.path.dirname(file_path)
    logger.debug(f"Ensuring database directory exists: {db_dir}")
    os.makedirs(db_dir, exist_ok=True)
    
    # Ensure file exists and is writable
    if not os.path.exists(file_path):
        logger.debug(f"Creating empty database file: {file_path}")
        with open(file_path, 'wb') as f:
            pass
    os.chmod(file_path, 0o666)
    
from app import app

if __name__ == "__main__":
    # Import models here to ensure they are registered with SQLAlchemy
    from models import User, Progress
    from app import db

    with app.app_context():
        # Create all database tables
        db.create_all()

    app.run(host="0.0.0.0", port=8080, debug=True)