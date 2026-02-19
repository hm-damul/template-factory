
import os
import re
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

def contains_korean(text: str) -> bool:
    return bool(re.search('[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f]', text))

def translate_to_english(text: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    print(f"DEBUG: API KEY found: {api_key[:10]}...")
    if not api_key:
        return "NO API KEY"
    
    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""Task: Translate the following text into professional marketing English.
CRITICAL: YOUR RESPONSE MUST BE 100% ENGLISH ONLY.
DO NOT INCLUDE ANY KOREAN CHARACTERS IN YOUR OUTPUT.

Input: {text}
English Output:"""
        
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=150
            )
        )
        return response.text.strip() if response.text else "EMPTY RESPONSE"
    except Exception as e:
        return f"ERROR: {e}"

test_text = "마이크로 SaaS 대시보드 UI (MVP)"
print(f"Input: {test_text}")
print(f"Contains Korean: {contains_korean(test_text)}")
result = translate_to_english(test_text)
print(f"Result: {result}")
