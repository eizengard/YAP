import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Check if OpenAI API key is set
openai_api_key = os.environ.get("OPENAI_API_KEY")
print(f"OPENAI_API_KEY is {'set and has value: ' + openai_api_key[:10] + '...' if openai_api_key else 'not set'}")

# Print other environment variables
print(f"DATABASE_URL: {os.environ.get('DATABASE_URL')}")
print(f"SESSION_SECRET: {os.environ.get('SESSION_SECRET')}")
print(f"FLASK_APP: {os.environ.get('FLASK_APP')}")
print(f"FLASK_ENV: {os.environ.get('FLASK_ENV')}") 