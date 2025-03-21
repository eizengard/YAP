from app import db
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    progress = db.relationship('Progress', backref='user', lazy=True)
    chats = db.relationship('Chat', backref='user', lazy=True)
    vocabulary_progress = db.relationship('VocabularyProgress', backref='user', lazy=True)
    preferences = db.relationship('UserPreferences', backref='user', uselist=False)
    daily_vocabulary = db.relationship('DailyVocabulary', backref='user', lazy=True)
    sentence_practices = db.relationship('SentencePractice', backref='user', lazy=True)
    speaking_attempts = db.relationship('UserSpeakingAttempt', backref='student', lazy=True)
    wallet_address = db.Column(db.String(42), unique=True)  # Ethereum addresses are 42 characters (with '0x')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'wallet_address': self.wallet_address,
            # Include other relevant fields
        }

class UserPreferences(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    target_language = db.Column(db.String(10), nullable=False)  # e.g., 'es', 'it'
    skill_level = db.Column(db.String(20), nullable=False)  # beginner, intermediate, advanced
    practice_duration = db.Column(db.Integer, nullable=False)  # minutes per day
    learning_goal = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Progress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    exercise_id = db.Column(db.String(50), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Chat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class VocabularyItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(100), nullable=False)
    translation = db.Column(db.String(100), nullable=False)
    language = db.Column(db.String(10), nullable=False)  # e.g., 'es', 'en', 'it'
    category = db.Column(db.String(50), nullable=False)  # e.g., 'greetings', 'food', 'numbers'
    difficulty = db.Column(db.Integer, default=1)  # 1: beginner, 2: intermediate, 3: advanced
    example_sentence = db.Column(db.Text)
    audio_url = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class VocabularyProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    vocabulary_id = db.Column(db.Integer, db.ForeignKey('vocabulary_item.id'), nullable=False)
    proficiency = db.Column(db.Integer, default=0)  # 0-100 score
    last_reviewed = db.Column(db.DateTime, default=datetime.utcnow)
    review_count = db.Column(db.Integer, default=0)
    next_review = db.Column(db.DateTime, default=datetime.utcnow)

class DailyVocabulary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    vocabulary_items = db.relationship('VocabularyItem', 
                                     secondary='daily_vocabulary_items',
                                     backref='daily_sets')

# Association table for daily vocabulary items
daily_vocabulary_items = db.Table('daily_vocabulary_items',
    db.Column('daily_vocab_id', db.Integer, db.ForeignKey('daily_vocabulary.id'), primary_key=True),
    db.Column('vocabulary_item_id', db.Integer, db.ForeignKey('vocabulary_item.id'), primary_key=True)
)

class SentencePractice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    vocabulary_item_id = db.Column(db.Integer, db.ForeignKey('vocabulary_item.id'), nullable=False)
    sentence = db.Column(db.Text, nullable=False)
    correction = db.Column(db.Text)
    feedback = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    vocabulary_item = db.relationship('VocabularyItem')

class SpeakingExercise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    scenario = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(20), nullable=False)  # beginner, intermediate, advanced
    category = db.Column(db.String(50), nullable=False)  # e.g., 'restaurant', 'travel', 'business'
    target_language = db.Column(db.String(10), nullable=False)
    example_audio_url = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UserSpeakingAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey('speaking_exercise.id'), nullable=False)
    audio_recording_url = db.Column(db.String(200))
    pronunciation_score = db.Column(db.Float)  # 0-100 score
    feedback = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    exercise = db.relationship('SpeakingExercise')