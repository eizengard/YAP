import os
import logging
from flask import Flask, render_template, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from flask_login import LoginManager, current_user
from gtts import gTTS
import tempfile
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy with the model class
db = SQLAlchemy(model_class=Base)

# Create the Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")

# Configure database
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL environment variable is not set")

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Import models after db initialization
from models import User, Progress, Chat # Added Chat model import
from utils.openai_helper import chat_with_ai, transcribe_audio

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat')
def chat():
    return render_template('chat.html')

@app.route('/exercises')
def exercises():
    return render_template('exercises.html')

@app.route('/api/chat', methods=['POST'])
def handle_chat():
    try:
        if not current_user.is_authenticated:
            return jsonify({'error': 'User not authenticated'}), 401

        data = request.json
        user_message = data.get('message')
        response = chat_with_ai(user_message)

        # Save the chat message and response
        chat = Chat(
            user_id=current_user.id,
            message=user_message,
            response=response,
            timestamp=datetime.utcnow() # Added timestamp
        )
        db.session.add(chat)
        db.session.commit()

        return jsonify({'response': response})
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return jsonify({'error': 'Failed to process chat message'}), 500

@app.route('/api/chat/history', methods=['GET'])
def get_chat_history():
    try:
        if not current_user.is_authenticated:
            return jsonify({'error': 'User not authenticated'}), 401

        chats = Chat.query.filter_by(user_id=current_user.id)\
            .order_by(Chat.timestamp.desc())\
            .limit(50)\
            .all()

        chat_history = [{
            'message': chat.message,
            'response': chat.response,
            'timestamp': chat.timestamp.isoformat()
        } for chat in chats]

        return jsonify({'history': chat_history})
    except Exception as e:
        logger.error(f"Chat history error: {str(e)}")
        return jsonify({'error': 'Failed to fetch chat history'}), 500

@app.route('/api/text-to-speech', methods=['POST'])
def text_to_speech():
    try:
        text = request.json.get('text')
        tts = gTTS(text=text, lang='en')

        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as fp:
            tts.save(fp.name)
            return jsonify({'audio_path': fp.name})
    except Exception as e:
        logger.error(f"TTS error: {str(e)}")
        return jsonify({'error': 'Text-to-speech conversion failed'}), 500

@app.route('/api/save-progress', methods=['POST'])
def save_progress():
    try:
        if not current_user.is_authenticated:
            return jsonify({'error': 'User not authenticated'}), 401

        data = request.json
        progress = Progress(
            user_id=current_user.id,
            exercise_id=data['exercise_id'],
            score=data['score']
        )
        db.session.add(progress)
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Progress save error: {str(e)}")
        return jsonify({'error': 'Failed to save progress'}), 500

with app.app_context():
    # Create all database tables
    db.create_all()
    logger.info("Database tables created successfully")