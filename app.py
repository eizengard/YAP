import os
import logging
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from gtts import gTTS
import tempfile
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

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
from models import User, Progress, Chat
from forms import LoginForm, RegisterForm
from utils.openai_helper import chat_with_ai, transcribe_audio

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('index'))
        flash('Invalid email or password', 'error')
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered', 'error')
            return render_template('register.html', form=form)

        if User.query.filter_by(username=form.username.data).first():
            flash('Username already taken', 'error')
            return render_template('register.html', form=form)

        user = User(
            username=form.username.data,
            email=form.email.data,
            password_hash=generate_password_hash(form.password.data)
        )
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/chat')
@login_required
def chat():
    return render_template('chat.html')

@app.route('/exercises')
@login_required
def exercises():
    return render_template('exercises.html')

@app.route('/api/chat', methods=['POST'])
@login_required
def handle_chat():
    try:
        data = request.json
        user_message = data.get('message')
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400

        logger.debug(f"Processing chat message: {user_message}")
        response = chat_with_ai(user_message)

        # Save the chat message and response
        chat = Chat(
            user_id=current_user.id,
            message=user_message,
            response=response,
            timestamp=datetime.utcnow()
        )
        db.session.add(chat)
        db.session.commit()
        logger.debug("Chat message saved successfully")

        return jsonify({'response': response})
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        db.session.rollback()  # Rollback the transaction in case of error
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat/history', methods=['GET'])
@login_required
def get_chat_history():
    try:
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
@login_required
def text_to_speech():
    try:
        text = request.json.get('text')
        lang = request.json.get('lang', 'en')  # Default to English
        accent = request.json.get('accent', 'com')  # Default to US accent

        if not text:
            return jsonify({'error': 'No text provided'}), 400

        # Configure TTS with enhanced parameters
        tts = gTTS(
            text=text,
            lang=lang,  # Use requested language
            lang_check=True,  # Enable language checking
            slow=False,  # Normal speed
            tld=accent  # Use requested accent (com=US, co.uk=British, ca=Canadian, etc.)
        )

        # Create temporary file with unique name
        audio_filename = f'tts_{datetime.utcnow().timestamp()}.mp3'
        audio_path = os.path.join('static', 'audio', audio_filename)

        # Ensure audio directory exists
        os.makedirs(os.path.join('static', 'audio'), exist_ok=True)

        # Save the audio file
        tts.save(audio_path)

        # Return the URL path to the audio file
        audio_url = url_for('static', filename=f'audio/{audio_filename}')
        return jsonify({
            'audio_url': audio_url,
            'lang': lang,
            'accent': accent
        })
    except Exception as e:
        logger.error(f"TTS error: {str(e)}")
        return jsonify({'error': 'Text-to-speech conversion failed'}), 500

@app.route('/api/save-progress', methods=['POST'])
@login_required
def save_progress():
    try:
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