from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, IntegerField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Log In')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

class UserPreferencesForm(FlaskForm):
    target_language = SelectField('Which language do you want to learn?',
        choices=[
            ('es', 'Spanish'),
            ('it', 'Italian'),
            ('fr', 'French'),
            ('de', 'German'),
            ('pt', 'Portuguese'),
            ('ja', 'Japanese'),
            ('ko', 'Korean'),
            ('zh', 'Mandarin Chinese'),
            ('ru', 'Russian'),
            ('ar', 'Arabic'),
            ('nl', 'Dutch'),
            ('pl', 'Polish'),
            ('tr', 'Turkish'),
            ('hi', 'Hindi'),
            ('vi', 'Vietnamese')
        ],
        validators=[DataRequired()]
    )

    skill_level = SelectField('What is your current skill level?',
        choices=[
            ('beginner', 'Beginner - Little to no knowledge'),
            ('intermediate', 'Intermediate - Can handle basic conversations'),
            ('advanced', 'Advanced - Comfortable with most situations')
        ],
        validators=[DataRequired()]
    )

    practice_duration = IntegerField('How many minutes per day do you plan to practice?',
        validators=[
            DataRequired(),
            NumberRange(min=5, max=180, message="Please choose between 5 and 180 minutes")
        ]
    )

    learning_goal = TextAreaField('Why are you learning this language?',
        validators=[
            DataRequired(),
            Length(min=10, max=500, message="Please provide a response between 10 and 500 characters")
        ]
    )

    submit = SubmitField('Start Learning')