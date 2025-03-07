import os
import logging
from openai import OpenAI

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY environment variable is not set")

openai = OpenAI(api_key=OPENAI_API_KEY)

def chat_with_ai(message):
    try:
        logger.debug(f"Sending message to OpenAI: {message}")
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful language learning assistant. Respond in a friendly and educational manner."},
                {"role": "user", "content": message}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenAI API error: {str(e)}")
        raise Exception(f"Failed to get response from OpenAI: {str(e)}")

def transcribe_audio(audio_file_path):
    try:
        logger.debug(f"Transcribing audio file: {audio_file_path}")
        with open(audio_file_path, "rb") as audio_file:
            response = openai.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        return response.text
    except Exception as e:
        logger.error(f"Audio transcription error: {str(e)}")
        raise Exception(f"Failed to transcribe audio: {str(e)}")
import os
import openai
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Initialize OpenAI client
try:
    API_KEY = os.environ.get("OPENAI_API_KEY")
    if not API_KEY:
        logger.warning("OPENAI_API_KEY not set. AI features will not work.")
    else:
        openai.api_key = API_KEY
except Exception as e:
    logger.error(f"Error initializing OpenAI: {str(e)}")

def chat_with_ai(message):
    """
    Send a message to OpenAI and get a response
    """
    try:
        if not openai.api_key:
            return "OpenAI API key not configured. Please contact the administrator."
        
        response = openai.Completion.create(
            model="gpt-3.5-turbo-instruct",
            prompt=f"User: {message}\nAssistant (as a friendly language tutor):",
            max_tokens=150,
            temperature=0.7,
        )
        
        return response.choices[0].text.strip()
    except Exception as e:
        logger.error(f"OpenAI error: {str(e)}")
        return "I'm having trouble processing your request. Please try again later."

def transcribe_audio(audio_file):
    """
    Transcribe audio using OpenAI's Whisper API
    """
    try:
        if not openai.api_key:
            return "OpenAI API key not configured. Please contact the administrator."
        
        transcript = openai.Audio.transcribe("whisper-1", audio_file)
        return transcript.text
    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        return "I couldn't transcribe the audio. Please try again."
