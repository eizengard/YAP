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
from flask_migrate import Migrate
from dynamic_auth import verify_dynamic_jwt
from flask_cors import CORS
from werkzeug.security import generate_password_hash

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
CORS(app)  # Enable CORS for all routes

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

# Initialize the database
db.init_app(app)

# Initialize Flask-Migrate
migrate = Migrate(app, db)

# Initialize extensions
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Import models after db initialization
from models import (
    User, Progress, Chat, VocabularyItem, VocabularyProgress, 
    UserPreferences, DailyVocabulary, SentencePractice, 
    SpeakingExercise, UserSpeakingAttempt
)
from forms import LoginForm, RegisterForm, UserPreferencesForm
from utils.openai_helper import chat_with_ai, transcribe_audio

@login_manager.user_loader
def load_user(user_id):
    """Load user and ensure preferences are correctly attached"""
    try:
        # Get the user from the database
        user = User.query.get(int(user_id))
        if not user:
            logger.error(f"User with ID {user_id} not found")
            return None
            
        # Debug output
        logger.info(f"Loading user {user.id} ({user.username})")
        
        # Check if this attribute exists (should always exist, but just in case)
        if not hasattr(user, 'preferences'):
            logger.error(f"User {user.id} does not have preferences attribute")
            return user
            
        # Clear any existing preferences reference to force a fresh query
        if user.preferences is not None:
            try:
                db.session.expunge(user.preferences)
                logger.debug(f"Expunged existing preferences for user {user.id}")
            except Exception as e:
                logger.error(f"Error expunging preferences: {str(e)}")
        
        # Explicitly load preferences to ensure we have the latest data
        try:
            fresh_prefs = UserPreferences.query.filter_by(user_id=user.id).first()
            
            if fresh_prefs:
                # Make sure preferences are attached to the user object
                user.preferences = fresh_prefs
                logger.debug(f"Loaded fresh preferences for user {user.id}: {fresh_prefs.target_language}")
            else:
                # Set preferences to None if not found
                user.preferences = None
                logger.debug(f"No preferences found for user {user.id}")
                
                # Attempt to create default preferences
                try:
                    logger.info(f"Creating default preferences for user {user.id}")
                    new_prefs = UserPreferences(
                        user_id=user.id,
                        target_language='es',  # Default to Spanish
                        skill_level='beginner',
                        practice_duration=15,
                        learning_goal='To improve my language skills'
                    )
                    db.session.add(new_prefs)
                    db.session.commit()
                    
                    # Now get the newly created preferences
                    user.preferences = UserPreferences.query.filter_by(user_id=user.id).first()
                    logger.info(f"Created and loaded default preferences for user {user.id}")
                except Exception as e:
                    logger.error(f"Failed to create default preferences: {str(e)}")
                    # Don't let this error stop user from logging in
                    pass
        except Exception as e:
            logger.error(f"Error loading preferences: {str(e)}")
            # Set preferences to None on error
            user.preferences = None
            
        # Return the user with preferences properly set
        return user
    except Exception as e:
        logger.error(f"Error in load_user: {str(e)}")
        return None

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

@app.route('/vocabulary-practice')
@login_required
def vocabulary_practice():
    try:
        # Check if user has preferences
        if not current_user.preferences:
            flash('Please set your language preferences first.', 'warning')
            return redirect(url_for('fix_preferences'))
        
        # Redirect to vocabulary route to ensure categories are displayed
        return redirect(url_for('vocabulary'))
    except Exception as e:
        flash('An error occurred: ' + str(e), 'danger')
        return redirect(url_for('fix_preferences'))

@app.route('/conversation-practice')
@login_required
def conversation_practice():
    try:
        # Debug info
        print(f"User ID: {current_user.id}, Username: {current_user.username}")
        print(f"Has preferences attr: {hasattr(current_user, 'preferences')}")
        
        if hasattr(current_user, 'preferences'):
            print(f"Preferences: {current_user.preferences}")
            
        # Ensure user has preferences
        if not hasattr(current_user, 'preferences') or current_user.preferences is None:
            # Try to load preferences explicitly
            prefs = UserPreferences.query.filter_by(user_id=current_user.id).first()
            if prefs:
                print(f"Found preferences, but not attached to user. Attaching now.")
                current_user.preferences = prefs
            else:
                print(f"No preferences found for user {current_user.id}")
                flash('Please set your language preferences first.', 'warning')
                return redirect(url_for('fix_preferences'))
        
        return render_template('chat.html')
    except Exception as e:
        import traceback
        print(f"Error in conversation_practice: {str(e)}")
        print(traceback.format_exc())
        flash('An error occurred: ' + str(e), 'danger')
        return redirect(url_for('fix_preferences'))

@app.route('/speaking-practice')
@login_required
def speaking_practice():
    try:
        # Debug info
        print(f"User ID: {current_user.id}, Username: {current_user.username}")
        print(f"Has preferences attr: {hasattr(current_user, 'preferences')}")
        
        if hasattr(current_user, 'preferences'):
            print(f"Preferences: {current_user.preferences}")
            
        # Ensure user has preferences
        if not hasattr(current_user, 'preferences') or current_user.preferences is None:
            # Try to load preferences explicitly
            prefs = UserPreferences.query.filter_by(user_id=current_user.id).first()
            if prefs:
                print(f"Found preferences, but not attached to user. Attaching now.")
                current_user.preferences = prefs
            else:
                print(f"No preferences found for user {current_user.id}")
                flash('Please set your language preferences first.', 'warning')
                return redirect(url_for('fix_preferences'))
            
        return render_template('exercises.html')
    except Exception as e:
        import traceback
        print(f"Error in speaking_practice: {str(e)}")
        print(traceback.format_exc())
        flash('An error occurred: ' + str(e), 'danger')
        return redirect(url_for('fix_preferences'))

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
@login_required
@csrf.exempt  # Exempt this endpoint from CSRF protection for API calls
def text_to_speech():
    try:
        data = request.get_json()
        text = data.get('text')
        lang = data.get('lang', 'es')  # Default to Spanish
        speed = data.get('speed', 0.8)  # Default to slightly slower
        model = data.get('model', 'tts-1')  # Default to standard model

        if not text or not text.strip():
            return jsonify({'error': 'No text provided'}), 400
            
        # Ensure text ends with proper punctuation for better TTS quality
        text = text.strip()
        if text and not text[-1] in '.!?':
            text = text + '.'
        
        logger.debug(f"Text-to-speech request - Text: {text[:30]}..., Language: {lang}")

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
        
        voice = language_voice_map.get(lang, 'alloy')  # Default to alloy if language not found
        logger.debug(f"Selected voice '{voice}' for language '{lang}'")
        
        # Create temporary file with unique name
        audio_filename = f'tts_{datetime.utcnow().timestamp()}.mp3'
        audio_dir = os.path.join('static', 'audio', 'tts')
        os.makedirs(audio_dir, exist_ok=True)
        audio_path = os.path.join(audio_dir, audio_filename)
        
        # Check if OpenAI API key is available
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        # Clean up key if it has line breaks or whitespace
        if openai_api_key:
            openai_api_key = openai_api_key.strip().replace('\n', '')
        
        if not openai_api_key:
            # Fall back to gTTS if no OpenAI API key is available
            logger.warning("No OpenAI API key available, falling back to gTTS")
            try:
                tts = gTTS(text=text, lang=lang, lang_check=False)  # Disable strict language check
                tts.save(audio_path)
            except Exception as gtts_error:
                logger.error(f"gTTS error: {str(gtts_error)}")
                return jsonify({'error': f'Failed to generate audio: {str(gtts_error)}'}), 500
        else:
            # Use OpenAI's TTS
            try:
                client = openai.OpenAI(api_key=openai_api_key)
                
                speech_file_response = client.audio.speech.create(
                    model=model,
                    voice=voice,
                    input=text,
                    speed=speed
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
                    tts = gTTS(text=text, lang=lang, lang_check=False)
                    tts.save(audio_path)
                    logger.debug(f"Fallback gTTS audio saved to: {audio_path}")
                except Exception as gtts_error:
                    logger.error(f"gTTS fallback error: {str(gtts_error)}")
                    return jsonify({'error': f'Both TTS methods failed: {str(openai_error)}, then {str(gtts_error)}'}), 500

        # Verify file was created and has content
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            logger.error(f"Audio file not created or empty: {audio_path}")
            return jsonify({'error': 'Failed to create audio file'}), 500
            
        # Return the URL path to the audio file
        audio_url = url_for('static', filename=f'audio/tts/{audio_filename}')
        return jsonify({
            'audio_url': audio_url,
            'text': text,
            'language': lang,
            'voice': voice
        })

    except Exception as e:
        logger.error(f"Error generating audio: {str(e)}")
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
    # Get the user's target language
    user_language = current_user.preferences.target_language if current_user.preferences else 'es'
    logger.debug(f"Loading vocabulary for language: {user_language}")
    
    # Get all vocabulary categories for the user's language
    categories = db.session.query(
        VocabularyItem.category,
        db.func.count(VocabularyItem.id).label('count')
    ).filter_by(language=user_language).group_by(VocabularyItem.category).all()

    # Format categories for display
    categories = [{'name': cat, 'count': count} for cat, count in categories]
    
    # Handle case when there are no categories yet for this language
    if not categories:
        # Check if there are any vocabulary items for this language
        lang_items = VocabularyItem.query.filter_by(language=user_language).count()
        logger.info(f"Found {lang_items} vocabulary items for language {user_language}")
        
        if lang_items == 0:
            # Force initialization for this specific language
            initialize_vocabulary_for_language(user_language)
            
            # Try fetching categories again for the user's language
            categories = db.session.query(
                VocabularyItem.category,
                db.func.count(VocabularyItem.id).label('count')
            ).filter_by(language=user_language).group_by(VocabularyItem.category).all()
            categories = [{'name': cat, 'count': count} for cat, count in categories]
        
        # If still no categories for this language, generate new words
        if not categories:
            try:
                logger.info(f"No vocabulary found for language {user_language}, generating new words")
                # Create a dummy request context for API call
                with app.test_request_context():
                    # Call the generate_vocabulary function
                    result = generate_vocabulary()
                    logger.debug(f"Generated vocabulary result: {result}")
                
                # Fetch categories again
                categories = db.session.query(
                    VocabularyItem.category,
                    db.func.count(VocabularyItem.id).label('count')
                ).filter_by(language=user_language).group_by(VocabularyItem.category).all()
                categories = [{'name': cat, 'count': count} for cat, count in categories]
            except Exception as e:
                logger.error(f"Error generating vocabulary for language {user_language}: {e}")
    
    # Get current category from query params, default to first category
    current_category = request.args.get('category')
    if not current_category and categories:
        current_category = categories[0]['name']
    
    # Calculate user's overall vocabulary progress
    progress = 50  # Default progress value
    try:
        # Fetch actual progress data if available
        user_progress = VocabularyProgress.query.filter_by(user_id=current_user.id).all()
        if user_progress:
            avg_proficiency = sum(p.proficiency for p in user_progress) / len(user_progress)
            progress = min(100, avg_proficiency)  # Cap at 100%
    except Exception as e:
        logger.error(f"Error calculating progress: {str(e)}")
    
    return render_template('vocabulary.html',
                         categories=categories,
                         current_category=current_category,
                         progress=progress,
                         user_language=user_language)  # Pass language to template

@app.route('/api/vocabulary/exercise')
@login_required
def get_vocabulary_exercise():
    try:
        mode = request.args.get('mode', 'flashcards')
        category = request.args.get('category')
        skip_cache = request.args.get('skip_cache', 'false').lower() == 'true'
        fallback = request.args.get('fallback', 'false').lower() == 'true'
        
        # If this is a fallback request, use a simplified approach
        if fallback:
            logger.info("Using fallback approach to get any vocabulary word")
            try:
                # Get user's language preference
                user_language = current_user.preferences.target_language if current_user.preferences else 'es'
                
                # Get any random word in the user's language
                word = VocabularyItem.query.filter_by(language=user_language).order_by(db.func.random()).first()
                
                if word:
                    return jsonify({
                        'id': word.id,
                        'word': word.word,
                        'translation': word.translation,
                        'language': word.language,
                        'example_sentence': word.example_sentence,
                        'category': word.category,
                    })
                else:
                    # If no words in user's language, get any word
                    word = VocabularyItem.query.order_by(db.func.random()).first()
                    if word:
                        return jsonify({
                            'id': word.id,
                            'word': word.word,
                            'translation': word.translation,
                            'language': word.language,
                            'example_sentence': word.example_sentence,
                            'category': word.category,
                        })
            except Exception as e:
                logger.error(f"Error in fallback vocabulary fetch: {str(e)}")
                # Continue to normal flow if fallback fails
        
        # Get user's language preference
        user_language = current_user.preferences.target_language if current_user.preferences else 'es'
        logger.debug(f"Loading vocabulary exercise for language: {user_language} and category: {category}")

        # Check if category has enough words and add more if needed
        if category:
            ensure_category_has_enough_words(user_language, category)

        # Safely get user's vocabulary progress
        progress = VocabularyProgress.query.filter_by(user_id=current_user.id).all()
        reviewed_ids = [p.vocabulary_id for p in progress]

        # Create or get the session list of recently seen words - with safer handling
        recently_seen = []
        try:
            if 'recently_seen_words' in session:
                recently_seen = session.get('recently_seen_words', [])
                if not isinstance(recently_seen, list):
                    recently_seen = []  # Reset if not a list
            logger.debug(f"Recently seen words: {recently_seen}")
        except Exception as e:
            logger.error(f"Error accessing session: {str(e)}")
            recently_seen = []  # Use empty list if session access fails
        
        # Prioritize words that haven't been reviewed or have low proficiency
        query = VocabularyItem.query.filter_by(language=user_language)  # Filter by language
        
        if category:
            query = query.filter_by(category=category)

        # Check if there are any matching words
        word_count = query.count()
        if word_count == 0:
            logger.warning(f"No vocabulary items found for language {user_language} and category {category}")
            return jsonify({'error': f'No vocabulary items available for {user_language}'}), 404

        # Get a list of all available word IDs
        all_word_ids = [item.id for item in query.all()]
        logger.debug(f"Found {len(all_word_ids)} words for category {category}")
        
        # Safely clear the recently seen list if we've seen all or most words
        if len(recently_seen) >= len(all_word_ids) or (len(recently_seen) > 0 and len(recently_seen) >= 0.7 * len(all_word_ids)):
            logger.debug(f"Clearing recently seen words list (seen {len(recently_seen)}/{len(all_word_ids)})")
            recently_seen = []
            
        # Simplified approach: just select a random word not in recently seen
        available_ids = [w_id for w_id in all_word_ids if w_id not in recently_seen]
        
        # If no unseen words available, just pick any random word
        if not available_ids:
            logger.debug("No unseen words available, picking any random word")
            word = query.order_by(db.func.random()).first()
        else:
            # Select a random word from available IDs
            chosen_id = random.choice(available_ids)
            word = query.filter_by(id=chosen_id).first()
            logger.debug(f"Selected word with ID {chosen_id}")
        
        if not word:
            logger.warning(f"No vocabulary item found even after fallback checks")
            return jsonify({'error': 'No vocabulary items available'}), 404

        # Add this word to recently seen with safer session handling
        try:
            if word.id not in recently_seen:
                recently_seen.append(word.id)
                # Keep only the 10 most recent words
                if len(recently_seen) > 10:
                    recently_seen.pop(0)
                session['recently_seen_words'] = recently_seen
                try:
                    session.modified = True
                except:
                    # Some session backends don't support this attribute
                    pass
                logger.debug(f"Added word ID {word.id} to recently seen, list now: {recently_seen}")
        except Exception as e:
            logger.error(f"Error updating session: {str(e)}")
            # Continue even if session update fails

        response = {
            'id': word.id,
            'word': word.word,
            'translation': word.translation,
            'language': word.language,
            'example_sentence': word.example_sentence,
            'category': word.category,
        }

        # Add distractors for multiple choice
        if mode == 'multiple-choice':
            # Get distractors from the same language
            distractors = VocabularyItem.query\
                .filter(VocabularyItem.id != word.id, VocabularyItem.language == user_language)\
                .order_by(db.func.random())\
                .limit(3)\
                .all()
                
            # If we don't have enough distractors, we might need to generate some
            if len(distractors) < 3:
                logger.debug(f"Not enough distractors found, using available {len(distractors)}")
                
            response['distractors'] = [d.translation for d in distractors]

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error getting vocabulary exercise: {str(e)}", exc_info=True)
        
        # Emergency fallback - get any word in any language as a last resort
        try:
            word = VocabularyItem.query.order_by(db.func.random()).first()
            if word:
                logger.info("Using emergency fallback to return any word")
                return jsonify({
                    'id': word.id,
                    'word': word.word,
                    'translation': word.translation,
                    'language': word.language,
                    'example_sentence': word.example_sentence,
                    'category': word.category or 'General',
                })
        except:
            pass
            
        return jsonify({'error': 'Failed to load exercise'}), 500

def ensure_category_has_enough_words(language, category):
    """Ensure a category has at least 5 words by adding more if needed."""
    if not category:
        return
        
    # Check if the category exists and has enough words
    word_count = VocabularyItem.query.filter_by(language=language, category=category).count()
    logger.debug(f"Category {category} for language {language} has {word_count} words")
    
    # If we have enough words, we're done
    if word_count >= 5:
        return
        
    # Add more words based on language and category
    additional_words = {}
    additional_words['fr'] = {
        'Food': [
            {"word": "fromage", "translation": "cheese", "example_sentence": "Je mange du pain avec du fromage."},
            {"word": "vin", "translation": "wine", "example_sentence": "Un verre de vin rouge, s'il vous plaît."},
            {"word": "café", "translation": "coffee", "example_sentence": "Je bois un café tous les matins."},
            {"word": "poisson", "translation": "fish", "example_sentence": "J'aime manger du poisson frais."},
            {"word": "légume", "translation": "vegetable", "example_sentence": "Il faut manger des légumes tous les jours."},
            {"word": "fruit", "translation": "fruit", "example_sentence": "Les fruits sont bons pour la santé."},
            {"word": "viande", "translation": "meat", "example_sentence": "Je ne mange pas beaucoup de viande."}
        ],
        'Greetings': [
            {"word": "bonsoir", "translation": "good evening", "example_sentence": "Bonsoir! Comment s'est passée votre journée?"},
            {"word": "s'il vous plaît", "translation": "please", "example_sentence": "S'il vous plaît, pouvez-vous m'aider?"},
            {"word": "excusez-moi", "translation": "excuse me", "example_sentence": "Excusez-moi, où est la banque?"},
            {"word": "enchanté", "translation": "nice to meet you", "example_sentence": "Enchanté de faire votre connaissance."},
            {"word": "à bientôt", "translation": "see you soon", "example_sentence": "À bientôt, mon ami!"}
        ],
        'Travel': [
            {"word": "avion", "translation": "airplane", "example_sentence": "Mon avion décolle à 14h."},
            {"word": "valise", "translation": "suitcase", "example_sentence": "Ma valise est trop lourde."},
            {"word": "billet", "translation": "ticket", "example_sentence": "J'ai acheté un billet pour Paris."},
            {"word": "voyage", "translation": "trip", "example_sentence": "J'ai fait un voyage en Italie l'année dernière."},
            {"word": "réservation", "translation": "reservation", "example_sentence": "J'ai une réservation pour deux personnes."}
        ],
        'Shopping': [
            {"word": "acheter", "translation": "to buy", "example_sentence": "Je veux acheter cette chemise."},
            {"word": "cher", "translation": "expensive", "example_sentence": "Ce restaurant est très cher."},
            {"word": "bon marché", "translation": "cheap", "example_sentence": "Ces chaussures sont bon marché."},
            {"word": "vendre", "translation": "to sell", "example_sentence": "Il veut vendre sa voiture."},
            {"word": "cadeau", "translation": "gift", "example_sentence": "C'est un cadeau pour mon ami."}
        ]
    }
    
    additional_words['es'] = {
        'Food': [
            {"word": "queso", "translation": "cheese", "example_sentence": "Me gusta el queso con pan."},
            {"word": "vino", "translation": "wine", "example_sentence": "Un vaso de vino tinto, por favor."},
            {"word": "café", "translation": "coffee", "example_sentence": "Tomo un café cada mañana."},
            {"word": "pescado", "translation": "fish", "example_sentence": "Me gusta comer pescado fresco."},
            {"word": "verdura", "translation": "vegetable", "example_sentence": "Es importante comer verduras todos los días."}
        ],
        'Greetings': [
            {"word": "buenas tardes", "translation": "good afternoon", "example_sentence": "¡Buenas tardes! ¿Cómo estás?"},
            {"word": "buenas noches", "translation": "good evening", "example_sentence": "¡Buenas noches! Que duermas bien."},
            {"word": "por favor", "translation": "please", "example_sentence": "Por favor, ¿puedes ayudarme?"},
            {"word": "disculpe", "translation": "excuse me", "example_sentence": "Disculpe, ¿dónde está el baño?"},
            {"word": "encantado", "translation": "pleased to meet you", "example_sentence": "Encantado de conocerte."}
        ],
        'Travel': [
            {"word": "avión", "translation": "airplane", "example_sentence": "Mi avión sale a las 2 de la tarde."},
            {"word": "maleta", "translation": "suitcase", "example_sentence": "Mi maleta es demasiado pesada."},
            {"word": "billete", "translation": "ticket", "example_sentence": "He comprado un billete para Madrid."},
            {"word": "viaje", "translation": "trip", "example_sentence": "Hice un viaje a México el año pasado."},
            {"word": "reserva", "translation": "reservation", "example_sentence": "Tengo una reserva para dos personas."}
        ],
        'Shopping': [
            {"word": "comprar", "translation": "to buy", "example_sentence": "Quiero comprar esta camisa."},
            {"word": "caro", "translation": "expensive", "example_sentence": "Este restaurante es muy caro."},
            {"word": "barato", "translation": "cheap", "example_sentence": "Estos zapatos son baratos."},
            {"word": "vender", "translation": "to sell", "example_sentence": "Él quiere vender su coche."},
            {"word": "regalo", "translation": "gift", "example_sentence": "Es un regalo para mi amigo."}
        ]
    }
    
    additional_words['de'] = {
        'Food': [
            {"word": "Käse", "translation": "cheese", "example_sentence": "Ich esse Brot mit Käse."},
            {"word": "Wein", "translation": "wine", "example_sentence": "Ein Glas Rotwein, bitte."},
            {"word": "Kaffee", "translation": "coffee", "example_sentence": "Ich trinke jeden Morgen Kaffee."},
            {"word": "Fisch", "translation": "fish", "example_sentence": "Ich esse gerne frischen Fisch."},
            {"word": "Gemüse", "translation": "vegetable", "example_sentence": "Man sollte jeden Tag Gemüse essen."}
        ],
        'Greetings': [
            {"word": "guten Tag", "translation": "good day", "example_sentence": "Guten Tag! Wie geht es Ihnen?"},
            {"word": "guten Abend", "translation": "good evening", "example_sentence": "Guten Abend! Wie war Ihr Tag?"},
            {"word": "bitte schön", "translation": "you're welcome", "example_sentence": "Danke. - Bitte schön!"},
            {"word": "tschüss", "translation": "bye", "example_sentence": "Tschüss, bis morgen!"},
            {"word": "entschuldigung", "translation": "excuse me", "example_sentence": "Entschuldigung, wo ist der Bahnhof?"}
        ],
        'Travel': [
            {"word": "Flugzeug", "translation": "airplane", "example_sentence": "Mein Flugzeug startet um 14 Uhr."},
            {"word": "Koffer", "translation": "suitcase", "example_sentence": "Mein Koffer ist zu schwer."},
            {"word": "Fahrkarte", "translation": "ticket", "example_sentence": "Ich habe eine Fahrkarte nach Berlin gekauft."},
            {"word": "Reise", "translation": "trip", "example_sentence": "Ich habe letztes Jahr eine Reise nach Italien gemacht."},
            {"word": "Reservierung", "translation": "reservation", "example_sentence": "Ich habe eine Reservierung für zwei Personen."}
        ],
        'Shopping': [
            {"word": "kaufen", "translation": "to buy", "example_sentence": "Ich möchte dieses Hemd kaufen."},
            {"word": "teuer", "translation": "expensive", "example_sentence": "Dieses Restaurant ist sehr teuer."},
            {"word": "billig", "translation": "cheap", "example_sentence": "Diese Schuhe sind billig."},
            {"word": "verkaufen", "translation": "to sell", "example_sentence": "Er will sein Auto verkaufen."},
            {"word": "Geschenk", "translation": "gift", "example_sentence": "Das ist ein Geschenk für meinen Freund."}
        ]
    }
    
    # Check if we have additional words for this language and category
    if language in additional_words and category in additional_words[language]:
        words_to_add = additional_words[language][category]
        
        # Find out how many more words we need
        words_needed = 5 - word_count
        words_to_add = words_to_add[:words_needed]  # Only take what we need
        
        # Add the words to the database
        for word_data in words_to_add:
            # Check if word already exists to avoid duplicates
            existing = VocabularyItem.query.filter_by(
                language=language, 
                category=category,
                word=word_data['word']
            ).first()
            
            if not existing:
                new_word = VocabularyItem(
                    language=language,
                    category=category,
                    word=word_data['word'],
                    translation=word_data['translation'],
                    example_sentence=word_data['example_sentence']
                )
                db.session.add(new_word)
        
        # Commit changes to database
        try:
            db.session.commit()
            logger.info(f"Added {len(words_to_add)} new words to {category} category for {language}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to add words to {category} category: {str(e)}")

@app.route('/api/vocabulary/progress', methods=['POST'])
@login_required
@csrf.exempt  # Exempt API endpoint from CSRF protection
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
            original_language = preferences.target_language if hasattr(preferences, 'target_language') else "none"
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
    try:
        # Debug info
        print(f"User ID: {current_user.id}, Username: {current_user.username}")
        print(f"Has preferences attr: {hasattr(current_user, 'preferences')}")
        
        if hasattr(current_user, 'preferences'):
            print(f"Preferences: {current_user.preferences}")
        
        # Always refresh the current user to get the latest preferences
        current_user_id = current_user.id
        fresh_user = User.query.get(current_user_id)
        fresh_preferences = UserPreferences.query.filter_by(user_id=current_user_id).first()
        
        print(f"Fresh user: {fresh_user}")
        print(f"Fresh preferences: {fresh_preferences}")
        
        # If user has no preferences, create default ones
        if not fresh_preferences:
            print(f"No preferences found for user {current_user.id}, creating defaults")
            fresh_preferences = UserPreferences(
                user_id=current_user.id,
                target_language='es',  # Default to Spanish
                skill_level='beginner',
                practice_duration=15,
                learning_goal='To improve my language skills'
            )
            db.session.add(fresh_preferences)
            db.session.commit()
            print(f"Created default preferences for user {current_user.id}")
            
            # Refresh preferences after commit
            fresh_preferences = UserPreferences.query.filter_by(user_id=current_user_id).first()
            
        # Update current_user.preferences for the session
        current_user.preferences = fresh_preferences
        
        if fresh_preferences:
            logger.debug(f"Profile page displaying preferences with language: {fresh_preferences.target_language}")
        
        # Get vocabulary statistics - wrapped in try/except for safety
        vocab_stats = {
            'total_words': 0,
            'mastered_words': 0
        }
        try:
            vocab_stats = {
                'total_words': VocabularyProgress.query.filter_by(user_id=current_user.id).count(),
                'mastered_words': VocabularyProgress.query.filter_by(
                    user_id=current_user.id
                ).filter(VocabularyProgress.proficiency >= 90).count()
            }
        except Exception as e:
            logger.error(f"Error getting vocabulary stats: {str(e)}")
            
        # Get speaking practice statistics - wrapped in try/except for safety
        speaking_stats = {
            'total_attempts': 0
        }
        try:
            speaking_stats = {
                'total_attempts': UserSpeakingAttempt.query.filter_by(user_id=current_user.id).count(),
            }
        except Exception as e:
            logger.error(f"Error getting speaking stats: {str(e)}")
            
        # Chat statistics
        chat_stats = {
            'total_messages': 0
        }
        try:
            chat_stats = {
                'total_messages': 0  # You can implement this based on your chat model
            } 
        except Exception as e:
            logger.error(f"Error getting chat stats: {str(e)}")
        
        # Get recent activities
        recent_activities = []
        
        return render_template('profile.html', 
                            fresh_preferences=fresh_preferences,
                            vocab_stats=vocab_stats,
                            speaking_stats=speaking_stats,
                            chat_stats=chat_stats,
                            recent_activities=recent_activities)
    except Exception as e:
        import traceback
        print(f"Error in profile: {str(e)}")
        print(traceback.format_exc())
        flash('An error occurred: ' + str(e), 'danger')
        return redirect(url_for('fix_preferences'))

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
        # Get the new language preference from the form
        new_language = request.form.get('target_language')
        
        if not new_language:
            flash('No language selected.', 'warning')
            return redirect(url_for('profile'))
        
        # Get or create the user's preferences
        preferences = UserPreferences.query.filter_by(user_id=current_user.id).first()
        
        if not preferences:
            # If user doesn't have preferences, create default ones
            preferences = UserPreferences(
                user_id=current_user.id,
                target_language=new_language,
                skill_level='beginner',
                practice_duration=15,
                learning_goal='To improve my language skills'
            )
            db.session.add(preferences)
            flash('New preferences created successfully.', 'success')
        else:
            # Otherwise update existing preferences
            try:
                original_language = preferences.target_language
            except AttributeError:
                original_language = "none"
            
            preferences.target_language = new_language
            flash(f'Language updated from {original_language} to {new_language}.', 'success')
        
        try:
            db.session.commit()
            
            # Get fresh preferences after commit
            db.session.expire_all()  # Expire all objects to ensure fresh data
            fresh_prefs = UserPreferences.query.filter_by(user_id=current_user.id).first()
            current_user.preferences = fresh_prefs  # Update current_user's preferences
            
            logger.debug(f"User session completely refreshed with new preferences: {fresh_prefs.target_language}")
            
            return redirect(url_for('profile'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating language: {str(e)}")
            flash(f'Error updating language: {str(e)}', 'danger')
            return redirect(url_for('profile'))
    
    except Exception as e:
        logger.error(f"Exception in update_language: {str(e)}")
        flash('An error occurred while updating your language preference.', 'danger')
        return redirect(url_for('profile'))

@app.route('/api/generate-vocabulary', methods=['POST'])
@login_required
def generate_vocabulary():
    """Generate new vocabulary words using OpenAI and add them to the user's daily set."""
    try:
        # Check if user has preferences
        if not current_user.preferences:
            logger.error("User has no preferences set")
            return jsonify({'error': 'Please set your language preferences first.'}), 400
            
        # Get user's language preferences  
        target_language = current_user.preferences.target_language
        skill_level = current_user.preferences.skill_level
        
        if not target_language:
            logger.error("User has no target language set")
            return jsonify({'error': 'Please set your target language in preferences.'}), 400
        
        # Log the request details
        logger.info(f"Generating vocabulary for user: {current_user.username}, language: {target_language}, level: {skill_level}")
        
        # Map skill level to difficulty
        difficulty_map = {
            'beginner': 1,
            'intermediate': 2,
            'advanced': 3
        }
        difficulty = difficulty_map.get(skill_level, 1)
        
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
        logger.debug(f"Translated language code '{target_language}' to language name '{language_name}'")
        
        # Use OpenAI to generate new vocabulary words
        prompt = f"""
        Generate 10 vocabulary words for a {skill_level} {language_name} language learner.
        The words should be in {language_name} (language code: {target_language}).
        
        For each word, provide:
        1. The word in {language_name}
        2. The English translation
        3. A simple example sentence using the word in {language_name}
        4. The category (choose from: Greetings, Food, Travel, Shopping, Numbers, School, Family, Colors, Animals, Time)
        
        Return the results in this JSON format:
        {{
            "vocabulary": [
                {{
                    "word": "word in {language_name}",
                    "translation": "English translation",
                    "example_sentence": "Example sentence in {language_name}",
                    "category": "category"
                }},
                ...
            ]
        }}
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
                data = json.loads(content)
                logger.debug(f"Successfully parsed JSON response: {type(data)}")
                
                # Extract vocabulary items from the response structure
                vocabulary_items = None
                if isinstance(data, dict):
                    if 'vocabulary' in data:
                        vocabulary_items = data['vocabulary']
                    elif 'words' in data:
                        vocabulary_items = data['words']
                    elif 'items' in data:
                        vocabulary_items = data['items']
                    else:
                        # Just get the first array in the response
                        for key, value in data.items():
                            if isinstance(value, list) and len(value) > 0:
                                vocabulary_items = value
                                break
                
                # If we didn't find any arrays, and data is a list, use it directly
                if vocabulary_items is None and isinstance(data, list):
                    vocabulary_items = data
                
                # If we still don't have vocabulary items, log and return error
                if vocabulary_items is None:
                    logger.error(f"Could not find vocabulary items in response: {content[:200]}...")
                    return jsonify({'error': 'Failed to parse vocabulary data structure'}), 500
                
                # Ensure vocabulary_items is a list before proceeding
                if not isinstance(vocabulary_items, list):
                    logger.error(f"Vocabulary items is not a list: {type(vocabulary_items)}")
                    return jsonify({'error': 'Invalid vocabulary data format'}), 500
                
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

@app.route('/api/auth/dynamic/callback', methods=['POST'])
def dynamic_auth_callback():
    data = request.get_json()
    token = data.get('token')
    wallet_address = data.get('walletAddress')
    
    if not wallet_address:
        return jsonify({'error': 'No wallet address provided'}), 400
    
    # In a real implementation, we would verify the JWT token
    # For now, we'll skip token verification since we're using a mock token
    
    # Look for existing user with this wallet
    user = User.query.filter_by(wallet_address=wallet_address).first()
    
    if not user:
        # Create a new user
        username = f"wallet_{wallet_address[:8]}"
        user = User(
            username=username,
            email=f"{username}@example.com",  # Generate a placeholder email
            wallet_address=wallet_address,
        )
        
        # Create default preferences for the new user
        preferences = UserPreferences(
            user=user,
            target_language='es',  # Default to Spanish
            skill_level='beginner',
            practice_duration=15,
            learning_goal='Learn a new language'
        )
        
        db.session.add(user)
        db.session.add(preferences)
        db.session.commit()
    
    # Log the user in
    login_user(user)
    
    return jsonify({
        'success': True,
        'user': user.to_dict(),
        'redirectUrl': '/exercises'  # Redirect to main app page
    })

@app.route('/api/auth/logout', methods=['POST'])
@login_required
def api_logout():
    logout_user()
    return jsonify({'success': True})

@app.route('/api/user/link-wallet', methods=['POST'])
@login_required
def link_wallet():
    data = request.get_json()
    wallet_address = data.get('wallet_address')
    
    if not wallet_address:
        return jsonify({'error': 'No wallet address provided'}), 400
    
    # Check if wallet is already linked to another account
    existing_user = User.query.filter_by(wallet_address=wallet_address).first()
    if existing_user and existing_user.id != current_user.id:
        return jsonify({'error': 'Wallet already linked to another account'}), 400
    
    # Link wallet to current user
    current_user.wallet_address = wallet_address
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/user/unlink-wallet', methods=['POST'])
@login_required
def unlink_wallet():
    if current_user.wallet_address:
        current_user.wallet_address = None
        db.session.commit()
        logout_user()
        return jsonify({'success': True, 'redirect': url_for('login')})
    return jsonify({'error': 'No wallet linked to this account'}), 400

@app.route('/wallet-login', methods=['POST'])
@csrf.exempt
def wallet_login():
    try:
        # Log debug information
        print(f"Request received: Content-Type: {request.headers.get('Content-Type')}")
        print(f"Request body: {request.get_data(as_text=True)}")
        
        # Check content type
        if not request.is_json:
            return jsonify({
                'error': 'Request must be JSON',
                'content_type': request.headers.get('Content-Type')
            }), 400
            
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        if 'wallet_address' not in data:
            return jsonify({'error': 'No wallet address provided', 'data': data}), 400

        wallet_address = data['wallet_address']
        print(f"Processing wallet address: {wallet_address}")
        
        # Check if user exists with this wallet
        user = User.query.filter_by(wallet_address=wallet_address).first()
        
        if not user:
            # Create new user with wallet
            username = f'user_{wallet_address[:8]}'  # Create a username from wallet address
            email = f'{wallet_address[:8]}@wallet.yap'  # Create a placeholder email
            
            print(f"Creating new user with wallet address: {wallet_address}")
            
            user = User(
                username=username,
                email=email,
                wallet_address=wallet_address
            )
            db.session.add(user)
            
            # Create default user preferences
            preferences = UserPreferences(
                user=user,
                target_language='es',  # Default to Spanish
                skill_level='beginner',
                practice_duration=15,
                learning_goal='To improve my language skills'
            )
            db.session.add(preferences)
            
            try:
                db.session.commit()
                print(f"New user created: {username}")
            except Exception as e:
                db.session.rollback()
                print(f"Error creating user: {str(e)}")
                return jsonify({'error': f'Failed to create user: {str(e)}'}), 500
        else:
            print(f"Existing user found: {user.username}")
        
        # Log in the user
        login_user(user)
        return jsonify({
            'success': True,
            'user': {
                'username': user.username,
                'email': user.email,
                'wallet_address': user.wallet_address
            }
        }), 200
        
    except Exception as e:
        import traceback
        print(f"Error in wallet_login: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/fix-preferences')
@login_required
def fix_preferences():
    """Special route to fix user preferences when they're missing"""
    try:
        # Check if the current user already has preferences
        if current_user.preferences:
            flash('Your preferences are already set.', 'info')
            return redirect(url_for('profile'))
        
        # Create default preferences for the user
        preferences = UserPreferences(
            user_id=current_user.id,
            target_language='es',  # Default to Spanish
            skill_level='beginner',
            practice_duration=15,
            learning_goal='To improve my language skills'
        )
        
        db.session.add(preferences)
        try:
            db.session.commit()
            flash('Default preferences have been created. Please customize them.', 'success')
            # Refresh the current user preferences
            fresh_prefs = UserPreferences.query.filter_by(user_id=current_user.id).first()
            current_user.preferences = fresh_prefs
            return redirect(url_for('preferences', edit=True))
        except Exception as e:
            db.session.rollback()
            flash('Failed to create preferences: ' + str(e), 'danger')
            return render_template('error.html', error=str(e))
            
    except Exception as e:
        flash('An error occurred: ' + str(e), 'danger')
        return render_template('error.html', error=str(e))

@app.route('/admin/fix-all-preferences')
def fix_all_preferences():
    """Admin utility to fix all users who don't have preferences"""
    try:
        # Find all users without preferences
        users_without_prefs = []
        all_users = User.query.all()
        fixed_count = 0
        error_count = 0
        
        for user in all_users:
            # Check if user has preferences
            prefs = UserPreferences.query.filter_by(user_id=user.id).first()
            if not prefs:
                users_without_prefs.append(user)
        
        # Create preferences for users without them
        for user in users_without_prefs:
            try:
                # Create default preferences
                preferences = UserPreferences(
                    user_id=user.id,
                    target_language='es',  # Default to Spanish
                    skill_level='beginner',
                    practice_duration=15,
                    learning_goal='To improve my language skills'
                )
                db.session.add(preferences)
                fixed_count += 1
                print(f"Created preferences for user {user.id} ({user.username})")
            except Exception as e:
                error_count += 1
                print(f"Error creating preferences for user {user.id}: {str(e)}")
        
        # Commit all changes
        if fixed_count > 0:
            try:
                db.session.commit()
                message = f"Fixed {fixed_count} users. Errors: {error_count}"
                print(message)
                return f"<h1>Success!</h1><p>{message}</p><p>Go back to <a href='/'>home</a>.</p>"
            except Exception as e:
                db.session.rollback()
                message = f"Database error: {str(e)}"
                print(message)
                return f"<h1>Database Error</h1><p>{message}</p>"
        else:
            return "<h1>No fixes needed</h1><p>All users have preferences. Go back to <a href='/'>home</a>.</p>"
    
    except Exception as e:
        message = f"Error in fix_all_preferences: {str(e)}"
        print(message)
        return f"<h1>Error</h1><p>{message}</p>"

def initialize_vocabulary_categories():
    """Initialize basic vocabulary categories if none exist."""
    # Check if we have any vocabulary items
    if VocabularyItem.query.count() == 0:
        logger.info("Initializing vocabulary categories...")
        
        # Define basic categories with sample words for different languages
        categories = {
            # Spanish vocabulary
            "es": {
                "Greetings": [
                    {"word": "hola", "translation": "hello", "example_sentence": "¡Hola! ¿Cómo estás?"},
                    {"word": "gracias", "translation": "thank you", "example_sentence": "Muchas gracias por tu ayuda."},
                    {"word": "adiós", "translation": "goodbye", "example_sentence": "Adiós, hasta mañana."}
                ],
                "Food": [
                    {"word": "pan", "translation": "bread", "example_sentence": "Me gusta el pan fresco."},
                    {"word": "agua", "translation": "water", "example_sentence": "Necesito un vaso de agua."},
                    {"word": "manzana", "translation": "apple", "example_sentence": "Como una manzana cada día."}
                ],
                "Travel": [
                    {"word": "hotel", "translation": "hotel", "example_sentence": "Estamos en un hotel bonito."},
                    {"word": "pasaporte", "translation": "passport", "example_sentence": "Necesito mi pasaporte para viajar."},
                    {"word": "tren", "translation": "train", "example_sentence": "El tren llega a las ocho."}
                ],
                "Shopping": [
                    {"word": "tienda", "translation": "store", "example_sentence": "Voy a la tienda a comprar ropa."},
                    {"word": "precio", "translation": "price", "example_sentence": "¿Cuál es el precio de esto?"},
                    {"word": "dinero", "translation": "money", "example_sentence": "No tengo suficiente dinero."}
                ]
            },
            # French vocabulary
            "fr": {
                "Greetings": [
                    {"word": "bonjour", "translation": "hello", "example_sentence": "Bonjour! Comment allez-vous?"},
                    {"word": "merci", "translation": "thank you", "example_sentence": "Merci beaucoup pour votre aide."},
                    {"word": "au revoir", "translation": "goodbye", "example_sentence": "Au revoir, à demain."}
                ],
                "Food": [
                    {"word": "pain", "translation": "bread", "example_sentence": "J'aime le pain frais."},
                    {"word": "eau", "translation": "water", "example_sentence": "J'ai besoin d'un verre d'eau."},
                    {"word": "pomme", "translation": "apple", "example_sentence": "Je mange une pomme chaque jour."}
                ],
                "Travel": [
                    {"word": "hôtel", "translation": "hotel", "example_sentence": "Nous sommes dans un bel hôtel."},
                    {"word": "passeport", "translation": "passport", "example_sentence": "J'ai besoin de mon passeport pour voyager."},
                    {"word": "train", "translation": "train", "example_sentence": "Le train arrive à huit heures."}
                ],
                "Shopping": [
                    {"word": "magasin", "translation": "store", "example_sentence": "Je vais au magasin pour acheter des vêtements."},
                    {"word": "prix", "translation": "price", "example_sentence": "Quel est le prix de ceci?"},
                    {"word": "argent", "translation": "money", "example_sentence": "Je n'ai pas assez d'argent."}
                ]
            },
            # German vocabulary
            "de": {
                "Greetings": [
                    {"word": "hallo", "translation": "hello", "example_sentence": "Hallo! Wie geht es dir?"},
                    {"word": "danke", "translation": "thank you", "example_sentence": "Vielen Dank für deine Hilfe."},
                    {"word": "auf Wiedersehen", "translation": "goodbye", "example_sentence": "Auf Wiedersehen, bis morgen."}
                ],
                "Food": [
                    {"word": "Brot", "translation": "bread", "example_sentence": "Ich mag frisches Brot."},
                    {"word": "Wasser", "translation": "water", "example_sentence": "Ich brauche ein Glas Wasser."},
                    {"word": "Apfel", "translation": "apple", "example_sentence": "Ich esse jeden Tag einen Apfel."}
                ],
                "Travel": [
                    {"word": "Hotel", "translation": "hotel", "example_sentence": "Wir sind in einem schönen Hotel."},
                    {"word": "Reisepass", "translation": "passport", "example_sentence": "Ich brauche meinen Reisepass zum Reisen."},
                    {"word": "Zug", "translation": "train", "example_sentence": "Der Zug kommt um acht Uhr an."}
                ],
                "Shopping": [
                    {"word": "Geschäft", "translation": "store", "example_sentence": "Ich gehe ins Geschäft, um Kleidung zu kaufen."},
                    {"word": "Preis", "translation": "price", "example_sentence": "Was ist der Preis dafür?"},
                    {"word": "Geld", "translation": "money", "example_sentence": "Ich habe nicht genug Geld."}
                ]
            },
            # Italian vocabulary
            "it": {
                "Greetings": [
                    {"word": "ciao", "translation": "hello", "example_sentence": "Ciao! Come stai?"},
                    {"word": "grazie", "translation": "thank you", "example_sentence": "Grazie mille per il tuo aiuto."},
                    {"word": "arrivederci", "translation": "goodbye", "example_sentence": "Arrivederci, a domani."}
                ],
                "Food": [
                    {"word": "pane", "translation": "bread", "example_sentence": "Mi piace il pane fresco."},
                    {"word": "acqua", "translation": "water", "example_sentence": "Ho bisogno di un bicchiere d'acqua."},
                    {"word": "mela", "translation": "apple", "example_sentence": "Mangio una mela ogni giorno."}
                ],
                "Travel": [
                    {"word": "albergo", "translation": "hotel", "example_sentence": "Siamo in un bell'albergo."},
                    {"word": "passaporto", "translation": "passport", "example_sentence": "Ho bisogno del mio passaporto per viaggiare."},
                    {"word": "treno", "translation": "train", "example_sentence": "Il treno arriva alle otto."}
                ],
                "Shopping": [
                    {"word": "negozio", "translation": "store", "example_sentence": "Vado al negozio per comprare vestiti."},
                    {"word": "prezzo", "translation": "price", "example_sentence": "Qual è il prezzo di questo?"},
                    {"word": "soldi", "translation": "money", "example_sentence": "Non ho abbastanza soldi."}
                ]
            }
        }
        
        # Add words to database for all supported languages
        for language, language_categories in categories.items():
            for category, words in language_categories.items():
                for word_data in words:
                    word = VocabularyItem(
                        word=word_data["word"],
                        translation=word_data["translation"],
                        example_sentence=word_data["example_sentence"],
                        language=language,
                        category=category,
                        difficulty=1  # Beginner level
                    )
                    db.session.add(word)
        
        try:
            db.session.commit()
            logger.info("Successfully initialized vocabulary categories for multiple languages")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error initializing vocabulary: {e}")
    else:
        logger.debug("Vocabulary items already exist, skipping initialization")

def initialize_vocabulary_for_language(language_code):
    """Initialize vocabulary categories for a specific language."""
    logger.info(f"Initializing vocabulary for language: {language_code}")
    
    # Define standard categories with sample words for different languages
    categories = {
        # Spanish vocabulary
        "es": {
            "Greetings": [
                {"word": "hola", "translation": "hello", "example_sentence": "¡Hola! ¿Cómo estás?"},
                {"word": "gracias", "translation": "thank you", "example_sentence": "Muchas gracias por tu ayuda."},
                {"word": "adiós", "translation": "goodbye", "example_sentence": "Adiós, hasta mañana."},
                {"word": "buenos días", "translation": "good morning", "example_sentence": "Buenos días, ¿cómo amaneciste?"},
                {"word": "buenas noches", "translation": "good night", "example_sentence": "Buenas noches, hasta mañana."},
                {"word": "por favor", "translation": "please", "example_sentence": "Por favor, pásame el libro."},
                {"word": "lo siento", "translation": "I'm sorry", "example_sentence": "Lo siento, fue mi culpa."}
            ],
            "Food": [
                {"word": "pan", "translation": "bread", "example_sentence": "Me gusta el pan fresco."},
                {"word": "agua", "translation": "water", "example_sentence": "Necesito un vaso de agua."},
                {"word": "manzana", "translation": "apple", "example_sentence": "Como una manzana cada día."},
                {"word": "leche", "translation": "milk", "example_sentence": "Bebo leche en el desayuno."},
                {"word": "arroz", "translation": "rice", "example_sentence": "El arroz es un alimento básico."},
                {"word": "carne", "translation": "meat", "example_sentence": "No como carne roja."},
                {"word": "queso", "translation": "cheese", "example_sentence": "El queso español es delicioso."}
            ],
            "Travel": [
                {"word": "hotel", "translation": "hotel", "example_sentence": "Estamos en un hotel bonito."},
                {"word": "pasaporte", "translation": "passport", "example_sentence": "Necesito mi pasaporte para viajar."},
                {"word": "tren", "translation": "train", "example_sentence": "El tren llega a las ocho."},
                {"word": "avión", "translation": "airplane", "example_sentence": "Viajaré en avión a Madrid."},
                {"word": "maleta", "translation": "suitcase", "example_sentence": "Mi maleta está demasiado pesada."},
                {"word": "mapa", "translation": "map", "example_sentence": "Según el mapa, el museo está cerca."},
                {"word": "playa", "translation": "beach", "example_sentence": "Pasamos el día en la playa."}
            ],
            "Shopping": [
                {"word": "tienda", "translation": "store", "example_sentence": "Voy a la tienda a comprar ropa."},
                {"word": "precio", "translation": "price", "example_sentence": "¿Cuál es el precio de esto?"},
                {"word": "dinero", "translation": "money", "example_sentence": "No tengo suficiente dinero."},
                {"word": "barato", "translation": "cheap", "example_sentence": "Este restaurante es bastante barato."},
                {"word": "caro", "translation": "expensive", "example_sentence": "El hotel es demasiado caro."},
                {"word": "tarjeta", "translation": "card", "example_sentence": "¿Puedo pagar con tarjeta?"},
                {"word": "descuento", "translation": "discount", "example_sentence": "Tienen un descuento del 20%."}
            ],
            "Education": [
                {"word": "escuela", "translation": "school", "example_sentence": "Mi escuela está cerca de mi casa."},
                {"word": "profesor", "translation": "teacher", "example_sentence": "Mi profesor de español es muy bueno."},
                {"word": "libro", "translation": "book", "example_sentence": "Este libro es interesante."},
                {"word": "estudiante", "translation": "student", "example_sentence": "Soy estudiante de medicina."},
                {"word": "clase", "translation": "class", "example_sentence": "La clase comienza a las 9."},
                {"word": "tarea", "translation": "homework", "example_sentence": "Tengo mucha tarea esta semana."},
                {"word": "examen", "translation": "exam", "example_sentence": "Mañana tengo un examen importante."}
            ]
        },
        # French vocabulary
        "fr": {
            "Greetings": [
                {"word": "bonjour", "translation": "hello", "example_sentence": "Bonjour! Comment allez-vous?"},
                {"word": "merci", "translation": "thank you", "example_sentence": "Merci beaucoup pour votre aide."},
                {"word": "au revoir", "translation": "goodbye", "example_sentence": "Au revoir, à demain."},
                {"word": "bonsoir", "translation": "good evening", "example_sentence": "Bonsoir! Comment s'est passée votre journée?"},
                {"word": "s'il vous plaît", "translation": "please", "example_sentence": "S'il vous plaît, pouvez-vous m'aider?"},
                {"word": "excusez-moi", "translation": "excuse me", "example_sentence": "Excusez-moi, où est la banque?"},
                {"word": "enchanté", "translation": "pleased to meet you", "example_sentence": "Enchanté de faire votre connaissance."}
            ],
            "Food": [
                {"word": "pain", "translation": "bread", "example_sentence": "J'aime le pain frais."},
                {"word": "eau", "translation": "water", "example_sentence": "J'ai besoin d'un verre d'eau."},
                {"word": "pomme", "translation": "apple", "example_sentence": "Je mange une pomme chaque jour."},
                {"word": "fromage", "translation": "cheese", "example_sentence": "Je mange du pain avec du fromage."},
                {"word": "vin", "translation": "wine", "example_sentence": "Un verre de vin rouge, s'il vous plaît."},
                {"word": "café", "translation": "coffee", "example_sentence": "Je bois un café tous les matins."}
            ],
            "Travel": [
                {"word": "hôtel", "translation": "hotel", "example_sentence": "Nous sommes dans un bel hôtel."},
                {"word": "passeport", "translation": "passport", "example_sentence": "J'ai besoin de mon passeport pour voyager."},
                {"word": "train", "translation": "train", "example_sentence": "Le train arrive à huit heures."},
                {"word": "avion", "translation": "airplane", "example_sentence": "Mon avion décolle à 14h."},
                {"word": "valise", "translation": "suitcase", "example_sentence": "Ma valise est trop lourde."}
            ],
            "Shopping": [
                {"word": "magasin", "translation": "store", "example_sentence": "Je vais au magasin pour acheter des vêtements."},
                {"word": "prix", "translation": "price", "example_sentence": "Quel est le prix de ceci?"},
                {"word": "argent", "translation": "money", "example_sentence": "Je n'ai pas assez d'argent."},
                {"word": "acheter", "translation": "to buy", "example_sentence": "Je veux acheter cette chemise."},
                {"word": "cher", "translation": "expensive", "example_sentence": "Ce restaurant est très cher."}
            ],
            "Education": [
                {"word": "école", "translation": "school", "example_sentence": "Mon fils va à l'école."},
                {"word": "professeur", "translation": "teacher", "example_sentence": "Le professeur explique la leçon."},
                {"word": "livre", "translation": "book", "example_sentence": "J'aime lire des livres."},
                {"word": "étudiant", "translation": "student", "example_sentence": "Je suis étudiant à l'université."},
                {"word": "classe", "translation": "class", "example_sentence": "La classe commence à 9 heures."},
                {"word": "examen", "translation": "exam", "example_sentence": "J'ai un examen demain."},
                {"word": "devoirs", "translation": "homework", "example_sentence": "Je dois faire mes devoirs ce soir."}
            ]
        },
        # German vocabulary
        "de": {
            "Greetings": [
                {"word": "hallo", "translation": "hello", "example_sentence": "Hallo! Wie geht es dir?"},
                {"word": "danke", "translation": "thank you", "example_sentence": "Vielen Dank für deine Hilfe."},
                {"word": "auf Wiedersehen", "translation": "goodbye", "example_sentence": "Auf Wiedersehen, bis morgen."},
                {"word": "guten Morgen", "translation": "good morning", "example_sentence": "Guten Morgen! Hast du gut geschlafen?"},
                {"word": "guten Abend", "translation": "good evening", "example_sentence": "Guten Abend! Wie war dein Tag?"},
                {"word": "bitte", "translation": "please", "example_sentence": "Bitte, kannst du mir helfen?"},
                {"word": "entschuldigung", "translation": "excuse me", "example_sentence": "Entschuldigung, wo ist der Bahnhof?"}
            ],
            "Food": [
                {"word": "Brot", "translation": "bread", "example_sentence": "Ich mag frisches Brot."},
                {"word": "Wasser", "translation": "water", "example_sentence": "Ich brauche ein Glas Wasser."},
                {"word": "Apfel", "translation": "apple", "example_sentence": "Ich esse jeden Tag einen Apfel."},
                {"word": "Käse", "translation": "cheese", "example_sentence": "Ich esse Brot mit Käse."},
                {"word": "Wein", "translation": "wine", "example_sentence": "Ein Glas Rotwein, bitte."}
            ],
            "Travel": [
                {"word": "Hotel", "translation": "hotel", "example_sentence": "Wir sind in einem schönen Hotel."},
                {"word": "Reisepass", "translation": "passport", "example_sentence": "Ich brauche meinen Reisepass zum Reisen."},
                {"word": "Zug", "translation": "train", "example_sentence": "Der Zug kommt um acht Uhr an."},
                {"word": "Flugzeug", "translation": "airplane", "example_sentence": "Das Flugzeug fliegt nach Berlin."},
                {"word": "Koffer", "translation": "suitcase", "example_sentence": "Mein Koffer ist zu schwer."},
                {"word": "Karte", "translation": "map", "example_sentence": "Hast du eine Karte von München?"},
                {"word": "Urlaub", "translation": "vacation", "example_sentence": "Wir machen nächste Woche Urlaub."}
            ],
            "Shopping": [
                {"word": "Geschäft", "translation": "store", "example_sentence": "Ich gehe ins Geschäft, um Kleidung zu kaufen."},
                {"word": "Preis", "translation": "price", "example_sentence": "Was ist der Preis dafür?"},
                {"word": "Geld", "translation": "money", "example_sentence": "Ich habe nicht genug Geld."},
                {"word": "teuer", "translation": "expensive", "example_sentence": "Dieses Restaurant ist sehr teuer."},
                {"word": "billig", "translation": "cheap", "example_sentence": "Diese Schuhe sind sehr billig."},
                {"word": "kaufen", "translation": "to buy", "example_sentence": "Ich möchte ein neues Handy kaufen."},
                {"word": "verkaufen", "translation": "to sell", "example_sentence": "Er will sein Auto verkaufen."}
            ],
            "Education": [
                {"word": "Schule", "translation": "school", "example_sentence": "Mein Sohn geht zur Schule."},
                {"word": "Lehrer", "translation": "teacher", "example_sentence": "Der Lehrer erklärt die Lektion."},
                {"word": "Buch", "translation": "book", "example_sentence": "Ich lese gerne Bücher."},
                {"word": "Student", "translation": "student", "example_sentence": "Ich bin Student an der Universität."},
                {"word": "Klasse", "translation": "class", "example_sentence": "Die Klasse beginnt um 9 Uhr."},
                {"word": "Prüfung", "translation": "exam", "example_sentence": "Ich habe morgen eine Prüfung."},
                {"word": "Hausaufgaben", "translation": "homework", "example_sentence": "Ich muss heute Abend meine Hausaufgaben machen."}
            ]
        },
        # Italian vocabulary
        "it": {
            "Greetings": [
                {"word": "ciao", "translation": "hello", "example_sentence": "Ciao! Come stai?"},
                {"word": "grazie", "translation": "thank you", "example_sentence": "Grazie mille per il tuo aiuto."},
                {"word": "arrivederci", "translation": "goodbye", "example_sentence": "Arrivederci, a domani."},
                {"word": "buongiorno", "translation": "good morning", "example_sentence": "Buongiorno! Come hai dormito?"},
                {"word": "buonasera", "translation": "good evening", "example_sentence": "Buonasera! Come è andata la giornata?"},
                {"word": "per favore", "translation": "please", "example_sentence": "Mi puoi aiutare, per favore?"},
                {"word": "scusa", "translation": "excuse me", "example_sentence": "Scusa, dov'è la stazione?"}
            ],
            "Food": [
                {"word": "pane", "translation": "bread", "example_sentence": "Mi piace il pane fresco."},
                {"word": "acqua", "translation": "water", "example_sentence": "Ho bisogno di un bicchiere d'acqua."},
                {"word": "mela", "translation": "apple", "example_sentence": "Mangio una mela ogni giorno."},
                {"word": "pasta", "translation": "pasta", "example_sentence": "La pasta italiana è famosa in tutto il mondo."},
                {"word": "pizza", "translation": "pizza", "example_sentence": "La pizza napoletana è la migliore."},
                {"word": "vino", "translation": "wine", "example_sentence": "Questo vino rosso è eccellente."},
                {"word": "caffè", "translation": "coffee", "example_sentence": "Gli italiani amano il caffè espresso."}
            ],
            "Travel": [
                {"word": "albergo", "translation": "hotel", "example_sentence": "Siamo in un bell'albergo."},
                {"word": "passaporto", "translation": "passport", "example_sentence": "Ho bisogno del mio passaporto per viaggiare."},
                {"word": "treno", "translation": "train", "example_sentence": "Il treno arriva alle otto."},
                {"word": "aereo", "translation": "airplane", "example_sentence": "Il mio aereo parte alle 15:00."},
                {"word": "valigia", "translation": "suitcase", "example_sentence": "La mia valigia è troppo pesante."},
                {"word": "biglietto", "translation": "ticket", "example_sentence": "Ho comprato un biglietto per Roma."},
                {"word": "vacanza", "translation": "vacation", "example_sentence": "Andiamo in vacanza domani."}
            ],
            "Shopping": [
                {"word": "negozio", "translation": "store", "example_sentence": "Vado al negozio per comprare vestiti."},
                {"word": "prezzo", "translation": "price", "example_sentence": "Qual è il prezzo di questo?"},
                {"word": "soldi", "translation": "money", "example_sentence": "Non ho abbastanza soldi."},
                {"word": "costoso", "translation": "expensive", "example_sentence": "Questo ristorante è molto costoso."},
                {"word": "economico", "translation": "cheap", "example_sentence": "Queste scarpe sono molto economiche."},
                {"word": "comprare", "translation": "to buy", "example_sentence": "Voglio comprare un nuovo telefono."},
                {"word": "vendere", "translation": "to sell", "example_sentence": "Lui vuole vendere la sua macchina."}
            ],
            "Education": [
                {"word": "scuola", "translation": "school", "example_sentence": "Mio figlio va a scuola."},
                {"word": "insegnante", "translation": "teacher", "example_sentence": "L'insegnante spiega la lezione."},
                {"word": "libro", "translation": "book", "example_sentence": "Mi piace leggere libri."},
                {"word": "studente", "translation": "student", "example_sentence": "Sono uno studente all'università."},
                {"word": "classe", "translation": "class", "example_sentence": "La classe inizia alle 9."},
                {"word": "esame", "translation": "exam", "example_sentence": "Ho un esame domani."},
                {"word": "compiti", "translation": "homework", "example_sentence": "Devo fare i compiti stasera."}
            ]
        }
    }
    
    # Check if the language is supported
    if language_code not in categories:
        logger.warning(f"Language {language_code} not supported for vocabulary initialization")
        # Default to English if language not supported
        return False
    
    try:
        # Add words to database for the specified language
        language_categories = categories[language_code]
        for category, words in language_categories.items():
            for word_data in words:
                word = VocabularyItem(
                    word=word_data["word"],
                    translation=word_data["translation"],
                    example_sentence=word_data["example_sentence"],
                    language=language_code,
                    category=category,
                    difficulty=1  # Beginner level
                )
                db.session.add(word)
        
        db.session.commit()
        logger.info(f"Successfully initialized vocabulary categories for {language_code}")
        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error initializing vocabulary for {language_code}: {e}")
        return False

# Initialize application
with app.app_context():
    db.create_all()
    # Call initialization functions in the correct order - vocabulary first, then speaking scenarios
    initialize_vocabulary_categories()
    # Now call the speaking initialization
    try:
        initialize_speaking_scenarios()
    except NameError as e:
        logger.error(f"Could not initialize speaking scenarios: {e}")
        # If there's an error, it's likely the function is defined in another module
        # or the function definition comes after this call