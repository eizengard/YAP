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