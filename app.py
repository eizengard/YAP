import os
import logging
import random
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from gtts import gTTS
import tempfile

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
from models import User, Progress, Chat, VocabularyItem, VocabularyProgress, UserPreferences
from forms import LoginForm, RegisterForm, UserPreferencesForm
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

        # Log the user in
        login_user(user)
        flash('Registration successful! Please tell us about your learning goals.', 'success')
        return redirect(url_for('preferences'))

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

# Add these routes after your existing routes
@app.route('/vocabulary')
@login_required
def vocabulary():
    categories = db.session.query(
        VocabularyItem.category,
        db.func.count(VocabularyItem.id).label('count')
    ).group_by(VocabularyItem.category).all()

    categories = [{'name': cat, 'count': count} for cat, count in categories]
    current_category = request.args.get('category', categories[0]['name'] if categories else None)

    return render_template('vocabulary.html',
                         categories=categories,
                         current_category=current_category)

@app.route('/api/vocabulary/exercise')
@login_required
def get_vocabulary_exercise():
    try:
        mode = request.args.get('mode', 'flashcards')
        category = request.args.get('category')

        # Get user's vocabulary progress
        progress = VocabularyProgress.query.filter_by(user_id=current_user.id).all()
        reviewed_ids = [p.vocabulary_id for p in progress]

        # Prioritize words that haven't been reviewed or have low proficiency
        query = VocabularyItem.query
        if category:
            query = query.filter_by(category=category)

        if reviewed_ids:
            # Mix of new and review words
            if random.random() < 0.7:  # 70% chance of new words
                word = query.filter(~VocabularyItem.id.in_(reviewed_ids))\
                          .order_by(db.func.random()).first()
            else:
                # Review words with low proficiency
                progress_ids = [p.vocabulary_id for p in progress if p.proficiency < 70]
                word = query.filter(VocabularyItem.id.in_(progress_ids))\
                          .order_by(db.func.random()).first()
        else:
            word = query.order_by(db.func.random()).first()

        if not word:
            return jsonify({'error': 'No vocabulary items available'}), 404

        response = {
            'id': word.id,
            'word': word.word,
            'translation': word.translation,
            'language': word.language,
            'example_sentence': word.example_sentence,
        }

        # Add distractors for multiple choice
        if mode == 'multiple-choice':
            distractors = VocabularyItem.query\
                .filter(VocabularyItem.id != word.id)\
                .order_by(db.func.random())\
                .limit(3)\
                .all()
            response['distractors'] = [d.translation for d in distractors]

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error getting vocabulary exercise: {str(e)}")
        return jsonify({'error': 'Failed to load exercise'}), 500

@app.route('/api/vocabulary/progress', methods=['POST'])
@login_required
def save_vocabulary_progress():
    try:
        data = request.json
        vocabulary_id = data['vocabulary_id']
        is_correct = data['correct']

        progress = VocabularyProgress.query\
            .filter_by(user_id=current_user.id, vocabulary_id=vocabulary_id)\
            .first()

        if not progress:
            progress = VocabularyProgress(
                user_id=current_user.id,
                vocabulary_id=vocabulary_id
            )
            db.session.add(progress)

        # Update proficiency
        if is_correct:
            progress.proficiency = min(100, progress.proficiency + 10)
        else:
            progress.proficiency = max(0, progress.proficiency - 5)

        progress.review_count += 1
        progress.last_reviewed = datetime.utcnow()

        # Set next review based on proficiency
        if progress.proficiency >= 90:
            days = 30
        elif progress.proficiency >= 70:
            days = 14
        elif progress.proficiency >= 50:
            days = 7
        else:
            days = 1

        progress.next_review = datetime.utcnow() + timedelta(days=days)

        db.session.commit()
        return jsonify({'status': 'success'})

    except Exception as e:
        logger.error(f"Error saving vocabulary progress: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to save progress'}), 500

@app.route('/preferences', methods=['GET', 'POST'])
@login_required
def preferences():
    # Check if user already has preferences
    if current_user.preferences and not request.args.get('edit'):
        return redirect(url_for('index'))

    form = UserPreferencesForm()
    if form.validate_on_submit():
        # Update existing preferences or create new ones
        preferences = current_user.preferences or UserPreferences(user_id=current_user.id)
        preferences.target_language = form.target_language.data
        preferences.skill_level = form.skill_level.data
        preferences.practice_duration = form.practice_duration.data
        preferences.learning_goal = form.learning_goal.data

        if not current_user.preferences:
            db.session.add(preferences)

        db.session.commit()
        flash('Your preferences have been saved!', 'success')
        return redirect(url_for('index'))

    # If user has existing preferences, pre-fill the form
    elif current_user.preferences and request.method == 'GET':
        form.target_language.data = current_user.preferences.target_language
        form.skill_level.data = current_user.preferences.skill_level
        form.practice_duration.data = current_user.preferences.practice_duration
        form.learning_goal.data = current_user.preferences.learning_goal

    return render_template('preferences.html', form=form)


from werkzeug.security import generate_password_hash, check_password_hash

with app.app_context():
    # Create all database tables
    db.create_all()
    logger.info("Database tables created successfully")