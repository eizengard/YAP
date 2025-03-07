from app import app

if __name__ == "__main__":
    # Import models here to ensure they are registered with SQLAlchemy
    from models import User, Progress
    from app import db

    with app.app_context():
        # Create all database tables
        db.create_all()

    app.run(host="0.0.0.0", port=5000, debug=True)