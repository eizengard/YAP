import os
import logging
import random
import json
import tempfile
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from gtts import gTTS
import tempfile
from sqlalchemy import func
import openai
from flask_wtf.csrf import CSRFProtect

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Debug database URL
logger.debug(f"DATABASE_URL: {os.environ.get('DATABASE_URL')}")

class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy with the model class
db = SQLAlchemy(model_class=Base)

# Create the Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Configure database
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL environment variable is not set")

# Ensure instance directory exists for SQLite
if database_url.startswith('sqlite:///'):
    db_path = database_url.replace('sqlite:///', '')
    if db_path.startswith('/'):
        # Absolute path
        db_dir = os.path.dirname(db_path)
    else:
        # Relative path
        db_dir = os.path.dirname(os.path.join(app.root_path, db_path))
    
    os.makedirs(db_dir, exist_ok=True)
    logger.debug(f"Ensured database directory exists: {db_dir}")

database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL environment variable is not set")
print("Using DATABASE_URL from environment:", database_url)  # Debugging output
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
from models import User, Progress, Chat, VocabularyItem, VocabularyProgress, UserPreferences, DailyVocabulary, SentencePractice, SpeakingExercise, UserSpeakingAttempt
from forms import LoginForm, RegisterForm, UserPreferencesForm
from utils.openai_helper import chat_with_ai, transcribe_audio

@login_manager.user_loader
def load_user(user_id):
    # Force a fresh database query by setting options(lazyload=True)
    # This ensures that relationships like preferences are always fetched fresh
    user = User.query.get(int(user_id))
    if user:
        # Explicitly load preferences to ensure we have the latest data
        if hasattr(user, 'preferences'):
            # Clear existing preference reference if any
            if user.preferences is not None:
                db.session.expunge(user.preferences)
            
            # Get fresh preferences
            fresh_prefs = UserPreferences.query.filter_by(user_id=user.id).first()
            if fresh_prefs:
                # Make sure preferences are attached to the user object
                user.preferences = fresh_prefs
                logger.debug(f"Loaded fresh preferences for user {user.id}: {fresh_prefs.target_language}")
    
    return user

@app.route('/')
def index():
    if current_user.is_authenticated:
        # Always refresh the current user to get the latest preferences
        user = User.query.get(current_user.id)
        if user and user.preferences:
            # Force refresh current_user.preferences
            fresh_preferences = UserPreferences.query.filter_by(user_id=user.id).first()
            if fresh_preferences:
                logger.debug(f"Fresh preferences loaded: {fresh_preferences.target_language}")
        
        # Get today's vocabulary set if user is logged in
        today = datetime.utcnow().date()
        daily_set = DailyVocabulary.query.filter_by(
            user_id=current_user.id,
            date=today
        ).first()

        # Get completed sentences
        completed_sentences = {}
        if daily_set:
            sentences = SentencePractice.query.filter(
                SentencePractice.user_id == current_user.id,
                SentencePractice.vocabulary_item_id.in_([w.id for w in daily_set.vocabulary_items])
            ).all()

            for sentence in sentences:
                completed_sentences[sentence.vocabulary_item_id] = {
                    'sentence': sentence.sentence,
                    'correction': sentence.correction,
                    'feedback': sentence.feedback
                }

        return render_template('index.html', 
                            daily_set=daily_set,
                            completed_sentences=completed_sentences)
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

        # Extract the content from the response dictionary
        response_content = response['content'] if isinstance(response, dict) else str(response)
        
        # Save the chat message and response
        chat = Chat(
            user_id=current_user.id,
            message=user_message,
            response=response_content,  # Store only the string content
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
def text_to_speech():
    try:
        data = request.get_json()
        text = data.get('text')
        lang = data.get('language', 'es')  # Default to Spanish
        voice = data.get('voice')  # Allow client to specify voice if desired
        
        if not text or not text.strip():
            return jsonify({'error': 'No text provided'}), 400

        # Normalize and improve text quality for TTS
        text = text.strip()
        if text and not text[-1] in '.!?':
            text = text + '.'
        
        # Try to detect the language from the text if not specified or mismatched
        # Basic language detection heuristics for common words/characters
        detected_lang = lang
        if not lang or lang == 'es':
            # Check for Italian words/phrases
            italian_markers = ['è', 'sono', 'mia', 'casa', 'molto', 'ciao', 'grazie', 'piacere', 'come stai']
            if any(marker in text.lower() for marker in italian_markers) and 'è' in text:
                detected_lang = 'it'
                logger.debug(f"Language detected as Italian instead of {lang}")
            
            # Check for French words/phrases
            french_markers = ['je suis', 'bonjour', 'merci', 'je', 'tu', 'nous', 'vous', 'très', 'beaucoup']
            if any(marker in text.lower() for marker in french_markers):
                detected_lang = 'fr'
                logger.debug(f"Language detected as French instead of {lang}")
            
            # Check for German words/phrases
            german_markers = ['ich', 'bin', 'du', 'ist', 'hallo', 'guten', 'danke', 'bitte', 'haus']
            if any(marker in text.lower() for marker in german_markers):
                detected_lang = 'de'
                logger.debug(f"Language detected as German instead of {lang}")
        
        logger.debug(f"TTS request - Text: {text[:30]}..., Language: {lang}, Detected: {detected_lang}, Voice: {voice}")

        # Map languages to appropriate OpenAI voices based on quality testing
        language_voice_map = {
            'es': 'nova',      # Spanish - nova has excellent Spanish pronunciation
            'it': 'alloy',     # Italian - alloy has better Italian articulation
            'fr': 'echo',      # French - echo handles French sounds well
            'de': 'fable',     # German - fable works for German
            'en': 'onyx',      # English - onyx is a warm English voice
            'pt': 'nova',      # Portuguese - similar enough to Spanish
            'ru': 'shimmer',   # Russian
            'zh': 'nova',      # Mandarin Chinese
            'ja': 'shimmer',   # Japanese
            'ko': 'shimmer',   # Korean
            'ar': 'nova',      # Arabic
            'nl': 'fable',     # Dutch
            'pl': 'fable',     # Polish
            'tr': 'alloy',     # Turkish
            'hi': 'nova',      # Hindi
            'vi': 'shimmer'    # Vietnamese
        }
        
        # Use provided voice or select based on detected language
        if not voice:
            voice = language_voice_map.get(detected_lang, 'alloy')  # Default to alloy if language not found
            
        logger.debug(f"Selected voice '{voice}' for language '{detected_lang}'")
        
        # Create temporary file with unique name
        audio_filename = f'tts_{datetime.utcnow().timestamp()}.mp3'
        audio_path = os.path.join('static', 'audio', 'tts', audio_filename)

        # Ensure audio directory exists
        os.makedirs(os.path.join('static', 'audio', 'tts'), exist_ok=True)
        
        # Check if OpenAI API key is available
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        # Clean up key if it has line breaks or whitespace
        if openai_api_key:
            openai_api_key = openai_api_key.strip().replace('\n', '')
        logger.debug(f"OpenAI API key available: {bool(openai_api_key)}")
        
        if not openai_api_key:
            # Fall back to gTTS if no OpenAI API key is available
            logger.warning("No OpenAI API key available, falling back to gTTS")
            try:
                tts = gTTS(text=text, lang=detected_lang, lang_check=False)  # Disable strict language check
                tts.save(audio_path)
            except Exception as gtts_error:
                logger.error(f"gTTS error: {str(gtts_error)}")
                # Try with Spanish as a fallback
                try:
                    fallback_lang = 'es'
                    logger.info(f"Trying fallback language {fallback_lang}")
                    tts = gTTS(text=text, lang=fallback_lang, lang_check=False)
                    tts.save(audio_path)
                except Exception as fallback_error:
                    logger.error(f"Fallback gTTS error: {str(fallback_error)}")
                    return jsonify({'error': f'Failed to generate audio: {str(gtts_error)}'}), 500
        else:
            # Use OpenAI's TTS
            try:
                client = openai.OpenAI(api_key=openai_api_key)
                
                # Determine which model to use
                # For short phrases use standard model (faster)
                # For complex content, longer texts, use HD model (better quality)
                model_to_use = "tts-1"
                if len(text) > 50 or any(lang in ('zh', 'ja', 'ko', 'ru', 'ar') for lang in [detected_lang]):
                    model_to_use = "tts-1-hd"  # Use HD for complex languages or longer texts
                
                speech_file_response = client.audio.speech.create(
                    model=model_to_use,
                    voice=voice,
                    input=text,
                    speed=0.85  # Slightly slower for better comprehension
                )
                
                # Save the file
                with open(audio_path, "wb") as file:
                    for chunk in speech_file_response.iter_bytes(chunk_size=1024):
                        file.write(chunk)
                
                logger.debug(f"OpenAI TTS audio saved to: {audio_path}")
            except Exception as openai_error:
                logger.error(f"OpenAI TTS error: {str(openai_error)}")
                
                # Fallback to gTTS if OpenAI fails
                logger.info(f"Falling back to gTTS after OpenAI error")
                try:
                    tts = gTTS(text=text, lang=detected_lang, lang_check=False)
                    tts.save(audio_path)
                    logger.debug(f"Fallback gTTS audio saved to: {audio_path}")
                except Exception as gtts_error:
                    logger.error(f"gTTS fallback error: {str(gtts_error)}")
                    return jsonify({'error': f'Both TTS methods failed: {str(openai_error)}, then {str(gtts_error)}'}), 500

        # Verify file was created and has content
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            logger.error(f"Audio file not created or empty: {audio_path}")
            return jsonify({'error': 'Failed to create audio file'}), 500
            
        logger.debug(f"Audio file created successfully: {audio_path}, size: {os.path.getsize(audio_path)} bytes")

        # Return the URL path to the audio file
        audio_url = url_for('static', filename=f'audio/tts/{audio_filename}')
        return jsonify({
            'audio_url': audio_url,
            'text': text,
            'language': detected_lang,
            'voice': voice
        })

    except Exception as e:
        logger.error(f"Error in text_to_speech route: {str(e)}")
        return jsonify({'error': f'Failed to generate audio: {str(e)}'}), 500

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
        return redirect(url_for('profile'))  # Changed to go to profile instead of index

    form = UserPreferencesForm()
    if form.validate_on_submit():
        try:
            logger.debug(f"Form submitted with data: {form.data}")
            # Update existing preferences or create new ones
            preferences = UserPreferences.query.filter_by(user_id=current_user.id).first()
            if not preferences:
                logger.debug("Creating new preferences")
                preferences = UserPreferences(user_id=current_user.id)
                db.session.add(preferences)
            else:
                logger.debug("Updating existing preferences")

            # Update the preferences fields
            original_language = preferences.target_language if preferences.target_language else "none"
            new_language = form.target_language.data
            preferences.target_language = new_language
            preferences.skill_level = form.skill_level.data
            preferences.practice_duration = form.practice_duration.data
            preferences.learning_goal = form.learning_goal.data
            preferences.updated_at = datetime.utcnow()

            logger.debug(f"About to commit preferences change from {original_language} to {new_language}")
            db.session.commit()
            logger.debug("Preferences saved successfully")
            
            # Store the user ID to reload after logout
            user_id = current_user.id
            
            # More aggressive session refresh
            from flask import session
            
            # Clear any existing Flask session data
            session.clear()
            
            # Log out the current user
            logout_user()
            
            # Reload the user from the database to get fresh data
            user = User.query.get(user_id)
            
            # Log the user back in
            login_user(user)
            
            # Force an explicit load of preferences to avoid caching issues
            fresh_prefs = UserPreferences.query.filter_by(user_id=user.id).first()
            logger.debug(f"User session completely refreshed with new preferences: {fresh_prefs.target_language}")
            
            # Include a cache-busting parameter in the redirect
            timestamp = int(datetime.utcnow().timestamp())
            flash('Your preferences have been saved!', 'success')
            return redirect(url_for('profile', _t=timestamp))  # Redirect to profile page with cache busting
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving preferences: {str(e)}")
            flash('An error occurred while saving your preferences.', 'error')
            return render_template('preferences.html', form=form)

    # If user has existing preferences, pre-fill the form
    elif current_user.preferences and request.method == 'GET':
        form.target_language.data = current_user.preferences.target_language
        form.skill_level.data = current_user.preferences.skill_level
        form.practice_duration.data = current_user.preferences.practice_duration
        form.learning_goal.data = current_user.preferences.learning_goal

    return render_template('preferences.html', form=form)


@app.route('/daily-practice')
@login_required
def daily_practice():
    # Check if user has set preferences
    if not current_user.preferences:
        flash('Please set your language preferences first.', 'warning')
        return redirect(url_for('preferences'))
        
    # Always refresh user preferences from database to get the latest language
    fresh_preferences = UserPreferences.query.filter_by(user_id=current_user.id).first()
    if fresh_preferences:
        # Log current language for debugging
        logger.debug(f"Daily practice loaded with language: {fresh_preferences.target_language}")
    else:
        logger.warning(f"No preferences found for user {current_user.id}")
        flash('Please set your language preferences first.', 'warning')
        return redirect(url_for('preferences'))

    # Get or create today's vocabulary set
    today = datetime.utcnow().date()
    daily_set = DailyVocabulary.query.filter_by(
        user_id=current_user.id,
        date=today
    ).first()

    # Check if there's a language mismatch before proceeding
    language_mismatch = False
    if daily_set and daily_set.vocabulary_items:
        item_languages = set(item.language for item in daily_set.vocabulary_items)
        if len(item_languages) > 1 or fresh_preferences.target_language not in item_languages:
            language_mismatch = True
            logger.debug(f"Language mismatch: vocabulary items are in {item_languages}, but user preference is {fresh_preferences.target_language}")
            
            # Clear the existing vocabulary items to force new ones for the current language
            daily_set.vocabulary_items = []
            db.session.commit()
            flash('Your language preference has changed. New vocabulary will be generated.', 'info')

    if not daily_set or not daily_set.vocabulary_items:
        # Create new daily set based on user's level
        if not daily_set:
            daily_set = DailyVocabulary(user_id=current_user.id, date=today)
            db.session.add(daily_set)

        # Get user's skill level
        user_level = fresh_preferences.skill_level
        difficulty_map = {
            'beginner': 1,
            'intermediate': 2,
            'advanced': 3
        }
        difficulty = difficulty_map.get(user_level, 1)

        # Get vocabulary items matching user's level and language
        words = VocabularyItem.query.filter_by(
            language=fresh_preferences.target_language,
            difficulty=difficulty
        ).order_by(db.func.random()).limit(10).all()

        if not words:
            flash('No vocabulary items available for your language and level. Please generate some new words.', 'warning')
            return render_template('daily_practice.html', daily_set=None, completed_sentences={}, language_mismatch=False)

        daily_set.vocabulary_items.extend(words)
        db.session.commit()
        logger.debug(f"Created daily set with {len(words)} words in language {fresh_preferences.target_language}")

    # Get completed sentences for today
    completed_sentences = {}
    sentences = SentencePractice.query.filter(
        SentencePractice.user_id == current_user.id,
        SentencePractice.vocabulary_item_id.in_([w.id for w in daily_set.vocabulary_items])
    ).all()

    for sentence in sentences:
        completed_sentences[sentence.vocabulary_item_id] = {
            'sentence': sentence.sentence,
            'correction': sentence.correction,
            'feedback': sentence.feedback
        }

    return render_template('daily_practice.html',
                         daily_set=daily_set,
                         completed_sentences=completed_sentences,
                         language_mismatch=language_mismatch)

@app.route('/submit-sentence', methods=['POST'])
@login_required
def submit_sentence():
    try:
        vocabulary_id = request.form.get('vocabulary_id')
        sentence = request.form.get('sentence', '').strip()

        if not vocabulary_id or not sentence:
            flash('Please provide a sentence.', 'error')
            return redirect(url_for('daily_practice'))

        # Get the vocabulary item
        vocab_item = VocabularyItem.query.get_or_404(vocabulary_id)

        # Use OpenAI to check the sentence and provide feedback
        prompt = f"""
        As a language tutor, evaluate this sentence using the word '{vocab_item.word}' 
        in {vocab_item.language}. The student's level is {current_user.preferences.skill_level}.

        Sentence: {sentence}

        Provide feedback in JSON format:
        {{
            "is_correct": true/false,
            "correction": "corrected sentence if needed, otherwise null",
            "feedback": "detailed feedback and suggestions"
        }}
        """

        response = chat_with_ai(prompt)
        feedback_data = json.loads(response)

        # Save the practice attempt
        practice = SentencePractice(
            user_id=current_user.id,
            vocabulary_item_id=vocabulary_id,
            sentence=sentence,
            correction=feedback_data.get('correction'),
            feedback=feedback_data.get('feedback')
        )

        db.session.add(practice)
        db.session.commit()

        flash('Sentence submitted successfully!', 'success')
        return redirect(url_for('daily_practice'))

    except Exception as e:
        logger.error(f"Error submitting sentence: {str(e)}")
        flash('An error occurred while submitting your sentence.', 'error')
        return redirect(url_for('daily_practice'))

from werkzeug.security import generate_password_hash, check_password_hash

def initialize_vocabulary():
    """Initialize vocabulary items if none exist."""
    if VocabularyItem.query.count() == 0:
        # Sample vocabulary items for different levels and languages
        items = [
            # Spanish - Beginner
            {
                'word': 'casa',
                'translation': 'house',
                'language': 'es',
                'category': 'basic',
                'difficulty': 1,
                'example_sentence': 'Mi casa es grande.'
            },
            {
                'word': 'perro',
                'translation': 'dog',
                'language': 'es',
                'category': 'animals',
                'difficulty': 1,
                'example_sentence': 'El perro es amigable.'
            },
            {
                'word': 'libro',
                'translation': 'book',
                'language': 'es',
                'category': 'basic',
                'difficulty': 1,
                'example_sentence': 'Me gusta leer este libro.'
            },
            # Spanish - Intermediate
            {
                'word': 'trabajo',
                'translation': 'work',
                'language': 'es',
                'category': 'basic',
                'difficulty': 2,
                'example_sentence': 'Me gusta mi trabajo.'
            },
            # Italian - Beginner
            {
                'word': 'casa',
                'translation': 'house',
                'language': 'it',
                'category': 'basic',
                'difficulty': 1,
                'example_sentence': 'La mia casa è grande.'
            },
            {
                'word': 'cane',
                'translation': 'dog',
                'language': 'it',
                'category': 'animals',
                'difficulty': 1,
                'example_sentence': 'Il cane è amichevole.'
            },
            # French - Beginner
            {
                'word': 'maison',
                'translation': 'house',
                'language': 'fr',
                'category': 'basic',
                'difficulty': 1,
                'example_sentence': 'Ma maison est grande.'
            },
            {
                'word': 'chien',
                'translation': 'dog',
                'language': 'fr',
                'category': 'animals',
                'difficulty': 1,
                'example_sentence': 'Le chien est amical.'
            },
            # German - Beginner
            {
                'word': 'Haus',
                'translation': 'house',
                'language': 'de',
                'category': 'basic',
                'difficulty': 1,
                'example_sentence': 'Mein Haus ist groß.'
            },
            {
                'word': 'Hund',
                'translation': 'dog',
                'language': 'de',
                'category': 'animals',
                'difficulty': 1,
                'example_sentence': 'Der Hund ist freundlich.'
            }
        ]

        for item in items:
            vocab_item = VocabularyItem(**item)
            db.session.add(vocab_item)

        try:
            db.session.commit()
            logger.info("Initialized vocabulary items")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error initializing vocabulary: {e}")

def initialize_speaking_scenarios():
    """Initialize speaking scenarios if none exist."""
    if SpeakingExercise.query.count() == 0:
        scenarios = [
            {
                'title': 'Ordering at a Restaurant',
                'scenario': 'You are at a restaurant and want to order your favorite meal. Practice ordering food, asking about ingredients, and making special requests.',
                'difficulty': 'beginner',
                'category': 'restaurant',
                'target_language': 'es',
            },
            {
                'title': 'Asking for Directions',
                'scenario': 'You are lost in a city and need to find your way to the train station. Practice asking for directions and understanding the responses.',
                'difficulty': 'beginner',
                'category': 'travel',
                'target_language': 'es',
            },
            {
                'title': 'Daily Greetings',
                'scenario': 'Practice common greetings and introductions for different times of day and situations.',
                'difficulty': 'beginner',
                'category': 'greetings',
                'target_language': 'es',
            },
            # Italian scenarios
            {
                'title': 'Al Ristorante',
                'scenario': 'Sei al ristorante e vuoi ordinare il tuo pasto preferito. Esercitati a ordinare cibo, chiedere informazioni sugli ingredienti e fare richieste speciali.',
                'difficulty': 'beginner',
                'category': 'restaurant',
                'target_language': 'it',
            },
            {
                'title': 'Chiedere Indicazioni',
                'scenario': 'Ti sei perso in città e devi trovare la stazione dei treni. Esercitati a chiedere indicazioni e capire le risposte.',
                'difficulty': 'beginner',
                'category': 'travel',
                'target_language': 'it',
            },
            {
                'title': 'Saluti Quotidiani',
                'scenario': 'Pratica i saluti comuni e le presentazioni per diversi momenti della giornata e situazioni.',
                'difficulty': 'beginner',
                'category': 'greetings',
                'target_language': 'it',
            }
        ]

        for scenario in scenarios:
            speaking_exercise = SpeakingExercise(**scenario)
            db.session.add(speaking_exercise)

        try:
            db.session.commit()
            logger.info("Initialized speaking scenarios")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error initializing speaking scenarios: {e}")

@app.route('/api/speaking/scenario/<scenario_id>')
@login_required
def get_speaking_scenario(scenario_id):
    try:
        # Get scenario based on user's preferences and skill level
        scenario = SpeakingExercise.query.filter_by(
            category=scenario_id,
            target_language=current_user.preferences.target_language,
            difficulty=current_user.preferences.skill_level
        ).first()

        if not scenario:
            # If no scenario exists for the exact level, get one close to user's level
            scenario = SpeakingExercise.query.filter_by(
                category=scenario_id,
                target_language=current_user.preferences.target_language
            ).first()

        if not scenario:
            return jsonify({'error': 'No scenario found'}), 404

        # Get conversation prompts and hints for the scenario based on language
        prompts = []
        hints = []
        if scenario.target_language == 'es':  # Spanish prompts
            if scenario.category == 'restaurant':
                prompts = [
                    "¡Hola! ¿Qué le gustaría ordenar hoy?",
                    "¿Desea alguna bebida con su comida?",
                    "¿Tiene alguna restricción dietética o pedido especial?",
                    "¿Le gustaría ordenar postre?"
                ]
                hints = [
                    "Me gustaría ordenar... / Quiero... / Para mí...",
                    "Sí, me gustaría... / No, gracias. / ¿Tienen...?",
                    "Soy vegetariano/a... / Soy alérgico/a a... / Sin...",
                    "Sí, ¿qué postres tienen? / No, gracias. La cuenta, por favor."
                ]
            elif scenario.category == 'travel':
                prompts = [
                    "Disculpe, ¿podría ayudarme a encontrar la estación de tren?",
                    "¿Cuánto tiempo se tarda en llegar allí?",
                    "¿Hay algún punto de referencia que deba buscar?",
                    "¿Cuál es la mejor manera de comprar los billetes?"
                ]
                hints = [
                    "¿Puede decirme cómo llegar a...? / ¿Dónde está...?",
                    "¿Está lejos? / ¿Cuántos minutos...?",
                    "¿Qué edificios...? / ¿Paso por...?",
                    "¿Dónde puedo comprar...? / ¿Hay una taquilla...?"
                ]
            elif scenario.category == 'greetings':
                prompts = [
                    "¡Buenos días! ¿Cómo está hoy?",
                    "¿Qué hizo durante el fin de semana?",
                    "¿Le gustaría tomar un café algún día?",
                    "¡Encantado de conocerle!"
                ]
                hints = [
                    "Muy bien, gracias. / Estoy... / Todo bien...",
                    "Fui a... / Estuve en... / Me quedé en casa...",
                    "Sí, me encantaría. / Che ne dice...?",
                    "¡Igualmente! / ¡Hasta pronto! / ¡Nos vemos!"
                ]
        elif scenario.target_language == 'it':  # Italian prompts
            if scenario.category == 'restaurant':
                prompts = [
                    "Buongiorno! Cosa desidera ordinare oggi?",
                    "Vuole qualcosa da bere con il pasto?",
                    "Ha delle restrizioni alimentari o richieste speciali?",
                    "Desidera ordinare un dessert?"
                ]
                hints = [
                    "Vorrei ordinare... / Per me... / Prendo...",
                    "Sì, vorrei... / No, grazie. / Avete...?",
                    "Sono vegetariano/a... / Sono allergico/a a... / Senza...",
                    "Sì, che dolci avete? / No, grazie. Il conto, per favore."
                ]
            elif scenario.category == 'travel':
                prompts = [
                    "Scusi, può aiutarmi a trovare la stazione dei treni?",
                    "Quanto tempo ci vuole per arrivarci?",
                    "Ci sono dei punti di riferimento che devo cercare?",
                    "Qual è il modo migliore per comprare i biglietti?"
                ]
                hints = [
                    "Mi può dire come arrivare a...? / Dov'è...?",
                    "È lontano? / Quanti minuti...?",
                    "Quali edifici...? / Devo passare...?",
                    "Dove posso comprare...? / C'è una biglietteria...?"
                ]
            elif scenario.category == 'greetings':
                prompts = [
                    "Buongiorno! Come sta oggi?",
                    "Cosa ha fatto durante il fine settimana?",
                    "Le piacerebbe prendere un caffè qualche volta?",
                    "È stato un piacere conoscerla!"
                ]
                hints = [
                    "Molto bene, grazie. / Sono... / Tutto bene...",
                    "Sono andato/a a... / Sono stato/a a... / Sono rimasto/a a casa...",
                    "Sì, mi piacerebbe molto. / Che ne dice...?",
                    "Altrettanto! / Arrivederci! / Ci vediamo!"
                ]

        return jsonify({
            'id': scenario.id,
            'title': scenario.title,
            'description': scenario.scenario,
            'example_audio_url': scenario.example_audio_url,
            'prompts': prompts,
            'hints': hints,
            'target_language': scenario.target_language
        })

    except Exception as e:
        logger.error(f"Error loading speaking scenario: {str(e)}")
        return jsonify({'error': 'Failed to load scenario'}), 500

@app.route('/api/speaking/submit', methods=['POST'])
@login_required
def submit_speaking_practice():
    try:
        if 'audio' not in request.files:
            logger.error("No audio file in request.files")
            return jsonify({'error': 'No audio file provided'}), 400

        audio_file = request.files['audio']
        logger.debug(f"Received audio file: {audio_file.filename}, mimetype: {audio_file.mimetype}")
        
        scenario_id = request.form.get('scenario_id')
        prompt_index = request.form.get('prompt_index', 0)

        if not scenario_id:
            logger.error("No scenario_id provided")
            return jsonify({'error': 'No scenario ID provided'}), 400

        # Save the audio file temporarily
        temp_audio_path = os.path.join(tempfile.gettempdir(), f'speaking_{datetime.utcnow().timestamp()}.webm')
        logger.debug(f"Saving audio to temporary file: {temp_audio_path}")
        audio_file.save(temp_audio_path)
        
        # Log file size and existence
        file_size = os.path.getsize(temp_audio_path) if os.path.exists(temp_audio_path) else "File does not exist"
        logger.debug(f"Temporary audio file size: {file_size} bytes")
        
        # Transcribe the audio using OpenAI's Whisper
        logger.debug(f"About to transcribe audio from path: {temp_audio_path}")
        try:
            transcription = transcribe_audio(temp_audio_path)
            logger.debug(f"Transcription result: {transcription}")
        except Exception as e:
            logger.error(f"Transcription error: {str(e)}")
            return jsonify({'error': f'Failed to transcribe audio: {str(e)}'}), 500

        # Get the scenario for comparison
        scenario = SpeakingExercise.query.get(scenario_id)
        if not scenario:
            logger.error(f"Scenario not found with ID: {scenario_id}")
            return jsonify({'error': 'Scenario not found'}), 404

        # Create prompt for pronunciation feedback
        prompt = f"""
        As a language tutor for {scenario.target_language}, evaluate this spoken response:
        Scenario: {scenario.scenario}
        Student's transcribed response: {transcription}

        Provide detailed feedback in JSON format:
        {{
            "pronunciation_score": float (0-100),
            "pronunciation_feedback": "specific feedback about pronunciation and accent",
            "grammar_feedback": "feedback about grammar usage",
            "vocabulary_feedback": "feedback about word choice and vocabulary",
            "fluency_score": float (0-100),
            "improvement_suggestions": ["list", "of", "specific", "suggestions"],
            "correct_response_example": "an example of a good response"
        }}
        """

        feedback_response = chat_with_ai(prompt)
        logger.debug(f"AI Feedback response: {feedback_response}")

        try:
            feedback_data = json.loads(feedback_response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI feedback: {e}")
            return jsonify({'error': 'Invalid feedback format'}), 500

        # Save the attempt in the database
        attempt = UserSpeakingAttempt(
            user_id=current_user.id,
            exercise_id=scenario_id,
            audio_recording_url=temp_audio_path,
            pronunciation_score=feedback_data['pronunciation_score'],
            feedback=json.dumps(feedback_data)
        )

        db.session.add(attempt)
        db.session.commit()

        # Clean up temporary audio file
        try:
            os.remove(temp_audio_path)
        except Exception as e:
            logger.warning(f"Failed to remove temporary audio file: {e}")

        return jsonify(feedback_data)

    except Exception as e:
        logger.error(f"Error processing speaking submission: {str(e)}")
        return jsonify({'error': 'Failed to process submission'}), 500

@app.route('/api/speaking/example-audio', methods=['POST'])
@login_required
def generate_example_audio():
    try:
        data = request.get_json()
        text = data.get('text')
        lang = data.get('language', 'es')  # Default to Spanish

        if not text or not text.strip():
            return jsonify({'error': 'No text provided'}), 400
            
        # Ensure text ends with proper punctuation for better TTS quality
        text = text.strip()
        if text and not text[-1] in '.!?':
            text = text + '.'
        
        # Try to detect the language from the text if not specified or mismatched
        # Basic language detection heuristics for common words/characters
        detected_lang = lang
        if not lang or lang == 'es':
            # Check for Italian words/phrases
            italian_markers = ['è', 'sono', 'mia', 'casa', 'molto', 'ciao', 'grazie', 'piacere', 'come stai']
            if any(marker in text.lower() for marker in italian_markers) and 'è' in text:
                detected_lang = 'it'
                logger.debug(f"Language detected as Italian instead of {lang}")
            
            # Check for French words/phrases
            french_markers = ['je suis', 'bonjour', 'merci', 'je', 'tu', 'nous', 'vous', 'très', 'beaucoup']
            if any(marker in text.lower() for marker in french_markers):
                detected_lang = 'fr'
                logger.debug(f"Language detected as French instead of {lang}")
            
            # Check for German words/phrases
            german_markers = ['ich', 'bin', 'du', 'ist', 'hallo', 'guten', 'danke', 'bitte', 'haus']
            if any(marker in text.lower() for marker in german_markers):
                detected_lang = 'de'
                logger.debug(f"Language detected as German instead of {lang}")
            
        logger.debug(f"Example audio request - Text: {text[:30]}..., Language: {lang}, Detected: {detected_lang}")

        # Map languages to appropriate OpenAI voices based on quality testing
        language_voice_map = {
            'es': 'nova',      # Spanish - nova has excellent Spanish pronunciation
            'it': 'alloy',     # Italian - alloy has better Italian articulation
            'fr': 'echo',      # French - echo handles French sounds well
            'de': 'fable',     # German - fable works for German
            'en': 'onyx',      # English - onyx is a warm English voice
            'pt': 'nova',      # Portuguese - similar enough to Spanish
            'ru': 'shimmer',   # Russian
            'zh': 'nova',      # Mandarin Chinese - nova has decent pronunciation
            'ja': 'shimmer',   # Japanese
            'ko': 'shimmer',   # Korean
            'ar': 'nova',      # Arabic
            'nl': 'fable',     # Dutch
            'pl': 'fable',     # Polish
            'tr': 'alloy',     # Turkish
            'hi': 'nova',      # Hindi
            'vi': 'shimmer'    # Vietnamese
        }
        
        voice = language_voice_map.get(detected_lang, 'alloy')  # Default to alloy if language not found
        logger.debug(f"Selected voice '{voice}' for language '{detected_lang}'")
        
        # Create temporary file with unique name
        audio_filename = f'example_{datetime.utcnow().timestamp()}.mp3'
        audio_path = os.path.join('static', 'audio', 'examples', audio_filename)

        # Ensure audio directory exists
        os.makedirs(os.path.join('static', 'audio', 'examples'), exist_ok=True)
        
        # Check if OpenAI API key is available
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        # Clean up key if it has line breaks or whitespace
        if openai_api_key:
            openai_api_key = openai_api_key.strip().replace('\n', '')
        logger.debug(f"OpenAI API key available: {bool(openai_api_key)}")
        
        if not openai_api_key:
            # Fall back to gTTS if no OpenAI API key is available
            logger.warning("No OpenAI API key available, falling back to gTTS")
            try:
                tts = gTTS(text=text, lang=detected_lang, lang_check=False)  # Disable strict language check
                tts.save(audio_path)
            except Exception as gtts_error:
                logger.error(f"gTTS error: {str(gtts_error)}")
                # Try with Spanish as a fallback
                try:
                    fallback_lang = 'es'
                    logger.info(f"Trying fallback language {fallback_lang}")
                    tts = gTTS(text=text, lang=fallback_lang, lang_check=False)
                    tts.save(audio_path)
                except Exception as fallback_error:
                    logger.error(f"Fallback gTTS error: {str(fallback_error)}")
                    return jsonify({'error': f'Failed to generate example audio: {str(gtts_error)}'}), 500
        else:
            # Use OpenAI's TTS
            try:
                client = openai.OpenAI(api_key=openai_api_key)
                
                # For complex phonetic languages, always use HD model
                model_to_use = "tts-1-hd"  # Always use high definition for examples
                
                speech_file_response = client.audio.speech.create(
                    model=model_to_use,
                    voice=voice,
                    input=text,
                    speed=0.75  # Slightly slower for better comprehension and learning
                )
                
                # Save the file
                with open(audio_path, "wb") as file:
                    for chunk in speech_file_response.iter_bytes(chunk_size=1024):
                        file.write(chunk)
                
                logger.debug(f"OpenAI TTS audio saved to: {audio_path}")
            except Exception as openai_error:
                logger.error(f"OpenAI TTS error: {str(openai_error)}")
                
                # Fallback to gTTS if OpenAI fails
                logger.info(f"Falling back to gTTS after OpenAI error")
                try:
                    # For fallback, don't enforce strict language checking
                    tts = gTTS(text=text, lang=detected_lang, lang_check=False)
                    tts.save(audio_path)
                    logger.debug(f"Fallback gTTS audio saved to: {audio_path}")
                except Exception as gtts_error:
                    logger.error(f"gTTS fallback error: {str(gtts_error)}")
                    return jsonify({'error': f'Both TTS methods failed: {str(openai_error)}, then {str(gtts_error)}'}), 500

        # Verify file was created and has content
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            logger.error(f"Audio file not created or empty: {audio_path}")
            return jsonify({'error': 'Failed to create audio file'}), 500
            
        logger.debug(f"Audio file created successfully: {audio_path}, size: {os.path.getsize(audio_path)} bytes")

        # Return the URL path to the audio file
        audio_url = url_for('static', filename=f'audio/examples/{audio_filename}')
        return jsonify({
            'audio_url': audio_url,
            'text': text,
            'language': detected_lang,
            'voice': voice
        })

    except Exception as e:
        logger.error(f"Error generating example audio: {str(e)}")
        return jsonify({'error': f'Failed to generate example audio: {str(e)}'}), 500

@app.route('/api/translate', methods=['POST'])
@login_required
def translate_text():
    try:
        data = request.json
        text = data.get('text')
        source_lang = data.get('source_lang', 'auto')
        target_lang = data.get('target_lang', 'en')
        
        if not text:
            return jsonify({'error': 'No text provided'}), 400
            
        # Create translation prompt
        prompt = f"""
        Translate the following text from {source_lang} to {target_lang}:
        
        {text}
        
        Only provide the translation, without any explanations or additional text.
        """
        
        # Use OpenAI's API for translation
        response = chat_with_ai(prompt)
        
        # Extract the text from the response
        translated_text = response
        if isinstance(response, dict) and 'content' in response:
            translated_text = response['content']
        
        # Trim whitespace and remove quotes if present
        translated_text = translated_text.strip()
        if translated_text.startswith('"') and translated_text.endswith('"'):
            translated_text = translated_text[1:-1]
        
        return jsonify({
            'original_text': text,
            'translated_text': translated_text,
            'source_lang': source_lang,
            'target_lang': target_lang
        })
        
    except Exception as e:
        logger.error(f"Translation error: {str(e)}")
        return jsonify({'error': f'Translation failed: {str(e)}'}), 500

@app.route('/profile')
@login_required
def profile():
    # Always refresh the current user to get the latest preferences
    current_user_id = current_user.id
    fresh_user = User.query.get(current_user_id)
    fresh_preferences = UserPreferences.query.filter_by(user_id=current_user_id).first()
    
    if fresh_preferences:
        logger.debug(f"Profile page displaying preferences with language: {fresh_preferences.target_language}")
    
    # Get vocabulary statistics
    vocab_stats = {
        'total_words': VocabularyProgress.query.filter_by(user_id=current_user.id).count(),
        'mastered_words': VocabularyProgress.query.filter_by(
            user_id=current_user.id
        ).filter(VocabularyProgress.proficiency >= 90).count()
    }

    # Get speaking practice statistics
    speaking_stats = {
        'total_attempts': UserSpeakingAttempt.query.filter_by(user_id=current_user.id).count(),
        'avg_score': db.session.query(
            func.avg(UserSpeakingAttempt.pronunciation_score)
        ).filter_by(user_id=current_user.id).scalar() or 0
    }

    # Get chat statistics
    chat_stats = {
        'total_messages': Chat.query.filter_by(user_id=current_user.id).count()
    }

    # Get recent activities
    recent_activities = []

    # Get recent speaking attempts
    speaking_attempts = UserSpeakingAttempt.query.filter_by(
        user_id=current_user.id
    ).order_by(UserSpeakingAttempt.created_at.desc()).limit(3).all()

    for attempt in speaking_attempts:
        recent_activities.append({
            'description': 'Speaking Practice',
            'details': f'Completed a speaking exercise with score: {attempt.pronunciation_score:.1f}%',
            'timestamp': attempt.created_at
        })

    # Get recent vocabulary progress
    vocab_progress = VocabularyProgress.query.filter_by(
        user_id=current_user.id
    ).order_by(VocabularyProgress.last_reviewed.desc()).limit(3).all()

    for progress in vocab_progress:
        vocab = VocabularyItem.query.get(progress.vocabulary_id)
        if vocab:
            recent_activities.append({
                'description': 'Vocabulary Practice',
                'details': f'Reviewed word: {vocab.word} (Proficiency: {progress.proficiency}%)',
                'timestamp': progress.last_reviewed
            })

    # Sort activities by timestamp
    recent_activities.sort(key=lambda x: x['timestamp'], reverse=True)
    recent_activities = recent_activities[:5]  # Keep only the 5 most recent activities
    
    # Pass fresh user data directly to the template
    return render_template('profile.html',
                         vocab_stats=vocab_stats,
                         speaking_stats=speaking_stats,
                         chat_stats=chat_stats,
                         recent_activities=recent_activities,
                         fresh_preferences=fresh_preferences)

@app.template_filter('datetime')
def format_datetime(value):
    """Format a datetime object to a readable string."""
    if not value:
        return ''

    now = datetime.utcnow()
    diff = now - value

    if diff < timedelta(minutes=1):
        return 'just now'
    elif diff < timedelta(hours=1):
        minutes = int(diff.total_seconds() / 60)
        return f'{minutes} minute{"s" if minutes != 1 else ""} ago'
    elif diff < timedelta(days=1):
        hours = int(diff.total_seconds() / 3600)
        return f'{hours} hour{"s" if hours != 1 else ""} ago'
    elif diff < timedelta(days=30):
        days = diff.days
        return f'{days} day{"s" if days != 1 else ""} ago'
    else:
        return value.strftime('%B %d, %Y')

@app.route('/update-language', methods=['POST'])
@login_required
def update_language():
    try:
        # Get the new target language from the form
        new_language = request.form.get('target_language')
        
        if not new_language:
            flash('No language selected.', 'error')
            return redirect(url_for('profile'))
            
        # Get user preferences
        preferences = UserPreferences.query.filter_by(user_id=current_user.id).first()
        
        if not preferences:
            flash('Please set your full preferences first.', 'warning')
            return redirect(url_for('preferences'))
            
        # Log the language change
        original_language = preferences.target_language
        logger.debug(f"Quick language update: {original_language} → {new_language}")
        
        # Update the language
        preferences.target_language = new_language
        preferences.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Just refresh database data without touching the session
        db.session.expire_all()
        
        # Save the updated language info in a flash message
        flash(f'Language preference updated to {new_language}!', 'success')
        logger.debug(f"User preferences updated to {new_language}")
        
        # Include a cache-busting parameter in the redirect
        timestamp = int(datetime.utcnow().timestamp())
        return redirect(url_for('profile', _t=timestamp))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating language preference: {str(e)}")
        flash('An error occurred while updating your language preference.', 'error')
        return redirect(url_for('profile'))

@app.route('/api/generate-vocabulary', methods=['POST'])
@login_required
def generate_vocabulary():
    """Generate new vocabulary words using OpenAI and add them to the user's daily set."""
    try:
        if not current_user.preferences:
            return jsonify({'error': 'Please set your language preferences first.'}), 400
            
        target_language = current_user.preferences.target_language
        skill_level = current_user.preferences.skill_level
        
        # Map skill level to difficulty
        difficulty_map = {
            'beginner': 1,
            'intermediate': 2,
            'advanced': 3
        }
        difficulty = difficulty_map.get(skill_level, 1)
        
        logger.debug(f"Generating vocabulary for language: {target_language}, level: {skill_level}")
        
        # Map language codes to full names for the prompt
        language_names = {
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German',
            'it': 'Italian',
            'pt': 'Portuguese',
            'ru': 'Russian',
            'zh': 'Mandarin Chinese',
            'ja': 'Japanese',
            'ko': 'Korean',
            'ar': 'Arabic'
        }
        
        language_name = language_names.get(target_language, target_language)
        
        # Use OpenAI to generate new vocabulary words
        prompt = f"""
        Generate 10 vocabulary words for a {skill_level} {language_name} language learner.
        For each word, provide:
        1. The word in {language_name}
        2. The English translation
        3. A simple example sentence using the word
        4. The category (e.g., 'food', 'travel', 'daily life', etc.)
        
        Return the results in this JSON format:
        [
            {{
                "word": "word in {language_name}",
                "translation": "English translation",
                "example_sentence": "Example sentence in {language_name}",
                "category": "category"
            }},
            ...
        ]
        """
        
        # Get API key - first check if we have one
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        if not openai_api_key:
            logger.error("OpenAI API key not available")
            return jsonify({'error': 'OpenAI API key not configured'}), 500
        
        # Clean up the API key if it contains newlines or extra whitespace
        openai_api_key = openai_api_key.strip().replace('\n', '')
        logger.debug(f"OpenAI API key available (length: {len(openai_api_key)})")
            
        try:
            # Use the OpenAI client to generate vocabulary
            client = openai.OpenAI(api_key=openai_api_key)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a helpful language learning assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            # Parse the response
            content = response.choices[0].message.content
            logger.debug(f"Received OpenAI response with content length: {len(content)}")
            
            # Try to parse the JSON with error handling
            try:
                vocabulary_items = json.loads(content)
                logger.debug(f"Successfully parsed JSON response of type: {type(vocabulary_items)}")
                
                # If we got a JSON object with a words array or other wrapper
                if isinstance(vocabulary_items, dict):
                    if 'words' in vocabulary_items:
                        vocabulary_items = vocabulary_items['words']
                    elif 'vocabulary' in vocabulary_items:
                        vocabulary_items = vocabulary_items['vocabulary']
                    elif 'items' in vocabulary_items:
                        vocabulary_items = vocabulary_items['items']
                    # If it's a dict but doesn't have expected keys, try converting values to a list
                    elif not isinstance(vocabulary_items, list):
                        vocabulary_items = list(vocabulary_items.values())
                
                # Ensure vocabulary_items is a list
                if not isinstance(vocabulary_items, list):
                    logger.error(f"Unexpected response format: {content[:200]}...")
                    return jsonify({'error': 'Failed to generate vocabulary: unexpected format'}), 500
                
                logger.debug(f"Final vocabulary items list has {len(vocabulary_items)} items")
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {str(e)}")
                logger.error(f"Raw content: {content[:200]}...")
                return jsonify({'error': 'Failed to parse vocabulary data'}), 500
            
            # Create or update the daily vocabulary set
            today = datetime.utcnow().date()
            
            # Delete any existing daily set for today
            daily_set = DailyVocabulary.query.filter_by(
                user_id=current_user.id,
                date=today
            ).first()
            
            if daily_set:
                # Clear existing vocabulary
                daily_set.vocabulary_items = []
            else:
                # Create new daily set
                daily_set = DailyVocabulary(user_id=current_user.id, date=today)
                db.session.add(daily_set)
            
            # Add new words to database
            for item in vocabulary_items:
                try:
                    # Create new vocabulary item
                    vocab_item = VocabularyItem(
                        word=item['word'],
                        translation=item['translation'],
                        language=target_language,
                        category=item.get('category', 'general'),  # Default to 'general' if category is missing
                        difficulty=difficulty,
                        example_sentence=item.get('example_sentence', '')  # Default to empty string if example is missing
                    )
                    db.session.add(vocab_item)
                    
                    # Add to daily set
                    daily_set.vocabulary_items.append(vocab_item)
                except KeyError as e:
                    logger.error(f"Missing required key in item: {str(e)}")
                    # Continue with other items even if one has an error
                    continue
            
            db.session.commit()
            logger.info(f"Generated {len(vocabulary_items)} new vocabulary items")
            
            return jsonify({'success': True, 'count': len(vocabulary_items)})
            
        except Exception as openai_error:
            logger.error(f"OpenAI API error: {str(openai_error)}")
            return jsonify({'error': f'Failed to generate vocabulary: {str(openai_error)}'}), 500
            
    except Exception as e:
        logger.error(f"Error generating vocabulary: {str(e)}")
        db.session.rollback()
        return jsonify({'error': f'Failed to generate vocabulary: {str(e)}'}), 500

with app.app_context():
    # Create all database tables
    db.create_all()
    logger.info("Database tables created successfully")
    initialize_vocabulary()
    initialize_speaking_scenarios()