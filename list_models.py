
import os
import re
from dotenv import load_dotenv
from google import genai

load_dotenv()

def list_models():
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("NO API KEY")
        return
    
    try:
        client = genai.Client(api_key=api_key)
        print("Available Models:")
        for model in client.models.list():
            print(f"- {model.name} (Supported actions: {model.supported_actions})")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    list_models()
