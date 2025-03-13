import os
import logging
import random
import json
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
from models import User, Progress, Chat, VocabularyItem, VocabularyProgress, UserPreferences, DailyVocabulary, SentencePractice
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


@app.route('/daily-practice')
@login_required
def daily_practice():
    # Check if user has set preferences
    if not current_user.preferences:
        flash('Please set your language preferences first.', 'warning')
        return redirect(url_for('preferences'))

    # Get or create today's vocabulary set
    today = datetime.utcnow().date()
    daily_set = DailyVocabulary.query.filter_by(
        user_id=current_user.id,
        date=today
    ).first()

    if not daily_set:
        # Create new daily set based on user's level
        daily_set = DailyVocabulary(user_id=current_user.id, date=today)

        # Get user's skill level
        user_level = current_user.preferences.skill_level
        difficulty_map = {
            'beginner': 1,
            'intermediate': 2,
            'advanced': 3
        }
        difficulty = difficulty_map.get(user_level, 1)

        # Get vocabulary items matching user's level and language
        words = VocabularyItem.query.filter_by(
            language=current_user.preferences.target_language,
            difficulty=difficulty
        ).order_by(db.func.random()).limit(10).all()

        if not words:
            flash('No vocabulary items available for your language and level.', 'warning')
            return redirect(url_for('index'))

        daily_set.vocabulary_items.extend(words)
        db.session.add(daily_set)
        db.session.commit()

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
                         completed_sentences=completed_sentences)

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

@app.route('/api/generate-vocabulary', methods=['POST'])
@login_required
def generate_vocabulary():
    try:
        if not current_user.preferences:
            return jsonify({'error': 'User preferences not set'}), 400

        language = current_user.preferences.target_language
        level = current_user.preferences.skill_level

        # Create a detailed prompt for OpenAI
        prompt = f"""
        As a language learning expert, generate 10 vocabulary words for {language} at {level} level.
        For each word, provide:
        1. The word in the target language
        2. English translation
        3. An example sentence using the word
        4. The difficulty level (1=beginner, 2=intermediate, 3=advanced)

        Return the data in JSON format like this:
        {{
            "vocabulary": [
                {{
                    "word": "word in target language",
                    "translation": "english translation",
                    "example_sentence": "example sentence in target language",
                    "difficulty": difficulty_level,
                    "category": "category name"
                }},
                ...
            ]
        }}
        """

        # Get response from OpenAI
        logger.debug(f"Sending message to OpenAI: {prompt}")
        response = chat_with_ai(prompt)
        logger.debug(f"Received response from OpenAI: {response}")
        data = json.loads(response)

        # Save new vocabulary items
        for item in data['vocabulary']:
            vocab_item = VocabularyItem(
                word=item['word'],
                translation=item['translation'],
                language=language,
                category=item.get('category', 'general'),
                difficulty=item['difficulty'],
                example_sentence=item['example_sentence']
            )
            db.session.add(vocab_item)

        db.session.commit()

        # Create or update daily vocabulary set
        today = datetime.utcnow().date()
        daily_set = DailyVocabulary.query.filter_by(
            user_id=current_user.id,
            date=today
        ).first()

        if not daily_set:
            daily_set = DailyVocabulary(user_id=current_user.id, date=today)
            db.session.add(daily_set)

        # Get newly created vocabulary items
        new_words = VocabularyItem.query.filter_by(
            language=language
        ).order_by(db.func.random()).limit(10).all()

        daily_set.vocabulary_items = new_words
        db.session.commit()

        return jsonify({'status': 'success', 'message': 'Vocabulary generated successfully'})

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}, Response: {response}")
        return jsonify({'error': 'Invalid response format from AI'}), 500
    except Exception as e:
        logger.error(f"Error generating vocabulary: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/translate', methods=['POST'])
@login_required
def translate_text():
    try:
        data = request.get_json()
        text = data.get('text')
        source_lang = data.get('source_lang')
        target_lang = data.get('target_lang', 'en')  # Default to English

        if not text or not source_lang:
            return jsonify({'error': 'Missing required parameters'}), 400

        # Create prompt for OpenAI
        prompt = f"""
        Translate the following text from {source_lang} to {target_lang}:
        Text: {text}

        Provide only the direct translation without any additional explanations.
        If the text is already in the target language, return it unchanged.
        """

        translation = chat_with_ai(prompt).strip()

        return jsonify({
            'translation': translation,
            'source_text': text,
            'source_lang': source_lang,
            'target_lang': target_lang
        })

    except Exception as e:
        logger.error(f"Translation error: {str(e)}")
        return jsonify({'error': str(e)}), 500

with app.app_context():
    # Create all database tables
    db.create_all()
    logger.info("Database tables created successfully")
    initialize_vocabulary()