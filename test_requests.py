
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

def test_api():
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        print("NO API KEY")
        return

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{
            "parts": [{"text": "Translate to English: 안녕하세요"}]
        }]
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_api()
