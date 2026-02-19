
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

def list_models():
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        print("NO API KEY")
        return

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
    try:
        response = requests.get(url)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            models = response.json().get('models', [])
            for m in models:
                print(f"- {m['name']}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_models()
