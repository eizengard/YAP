import os
import logging
from openai import OpenAI, OpenAIError

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
use_mock = False

if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY environment variable is not set. Using mock implementation.")
    use_mock = True
else:
    openai = OpenAI(api_key=OPENAI_API_KEY)


def chat_with_ai(message):
    if use_mock:
        logger.info(f"Mock response for: {message}")
        return {
            "role": "assistant",
            "content": "This is a mock response as no OpenAI API key is set. To use the real API, please set the OPENAI_API_KEY environment variable."
        }
        
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
                "You are an AI language tutor designed to help learners become more fluent in their target language. Your role is to be patient, warm, and engaging, making conversations feel natural and human-like. You should: Respond in a friendly and encouraging manner. Adapt to the learner's proficiency level and provide helpful corrections when needed. Provide cultural and current news updates when asked, ensuring that the learner stays informed about relevant topics. Keep the conversation engaging by asking follow-up questions and making small talk when appropriate. Avoid robotic or overly formal speech; instead, mimic a casual and natural conversational style. Explain words, phrases, or cultural references in a way that is easy for the learner to understand. Encourage learners to express themselves fully and confidently. Stay supportive and never criticize mistakes harshly. Your goal is to help the learner gain fluency while making the learning experience enjoyable."
            }, {
                "role": "user",
                "content": message
            }])

        logger.debug(f"OpenAI response: {completion}")
        response = completion.choices[0].message

        return {"role": response.role, "content": response.content}
    except OpenAIError as e:
        logger.error(f"OpenAI API error: {e}")
        return {
            "role": "assistant",
            "content": "I'm sorry, I'm having trouble processing your request right now. Please try again later."
        }
    except Exception as e:
        logger.error(f"Error in chat_with_ai: {e}")
        return {
            "role": "assistant",
            "content": "An unexpected error occurred. Please try again."
        }


def transcribe_audio(audio_file_path):
    if use_mock:
        logger.info(f"Mock transcription for file: {audio_file_path}")
        return "This is a mock transcription as no OpenAI API key is set. To use the real API, please set the OPENAI_API_KEY environment variable."
        
    try:
        logger.debug(f"Transcribing audio file: {audio_file_path}")
        
        # Check if file exists and is not empty
        if not os.path.exists(audio_file_path):
            logger.error(f"Audio file does not exist: {audio_file_path}")
            return "Error: Audio file not found"
            
        file_size = os.path.getsize(audio_file_path)
        if file_size == 0:
            logger.error(f"Audio file is empty (0 bytes): {audio_file_path}")
            return "Error: Audio file is empty"
            
        logger.debug(f"Audio file size: {file_size} bytes")
        
        # Convert webm to mp3 format if needed
        if audio_file_path.endswith('.webm'):
            try:
                # Try using a direct approach first
                with open(audio_file_path, "rb") as audio_file:
                    transcript = openai.audio.transcriptions.create(
                        model="whisper-1", 
                        file=audio_file
                    )
                    
                logger.debug(f"Direct transcription result: {transcript}")
                return transcript.text
            except Exception as e:
                logger.error(f"Direct transcription failed: {e}. Using fallback transcription.")
                # Fallback to simpler text for troubleshooting
                return "This is a fallback transcription. The audio could not be processed."
        else:
            # Standard processing for non-webm files
            with open(audio_file_path, "rb") as audio_file:
                transcript = openai.audio.transcriptions.create(
                    model="whisper-1", 
                    file=audio_file
                )
                
            logger.debug(f"Transcription result: {transcript}")
            return transcript.text
    except OpenAIError as e:
        logger.error(f"OpenAI API error during transcription: {e}")
        return f"Error transcribing audio: {str(e)}"
    except Exception as e:
        logger.error(f"Error in transcribe_audio: {e}")
        return f"An unexpected error occurred during transcription: {str(e)}"