import os
import logging
from openai import OpenAI, OpenAIError

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY environment variable is not set")

openai = OpenAI(api_key=OPENAI_API_KEY)


def chat_with_ai(message):
    try:
        logger.debug(f"Sending message to OpenAI: {message}")

        if not message.strip():
            raise ValueError("Empty message received")

        completion = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{
                "role":
                "system",
                "content":
                "You are a highly effective and friendly language learning tutor. Your tone is warm, natural, and conversational. Provide clear, concise explanations and engaging practice exercises. Adapt your responses based on the learner's level in Spanish, Italian, or English. Gently correct mistakes and suggest alternative expressions. Ask follow-up questions to encourage practice and check for understanding. Your goal is to make language learning immersive, enjoyable, and effective while sounding like a supportive, real human tutor. Remember to always provide a detailed explanation of the concept, its pronunciation, and any relevant examples or exercises. Use active language and avoid using jargon or technical terms. Ask for clarification when needed and provide helpful feedback."
            }, {
                "role": "user",
                "content": message
            }],
            temperature=0.7,
            max_tokens=1000,  # Increased token limit for vocabulary generation
            response_format={"type": "text"})  # Allow free-form text for vocabulary generation

        if not completion.choices or not completion.choices[0].message:
            logger.error("No valid response received from OpenAI")
            raise ValueError("Invalid response from OpenAI")

        response = completion.choices[0].message.content.strip()
        logger.debug(f"Received response from OpenAI: {response[:100]}...")
        return response

    except OpenAIError as e:
        logger.error(f"OpenAI API error: {str(e)}")
        raise Exception(f"OpenAI API error: {str(e)}")
    except Exception as e:
        logger.error(f"Error in chat_with_ai: {str(e)}")
        raise Exception(f"Failed to get response: {str(e)}")


def transcribe_audio(audio_file_path):
    try:
        logger.debug(f"Transcribing audio file: {audio_file_path}")
        with open(audio_file_path, "rb") as audio_file:
            response = openai.audio.transcriptions.create(model="whisper-1",
                                                          file=audio_file)
        return response.text
    except Exception as e:
        logger.error(f"Audio transcription error: {str(e)}")
        raise Exception(f"Failed to transcribe audio: {str(e)}")