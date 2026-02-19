
import os
from dotenv import load_dotenv
load_dotenv()
key = os.getenv("GEMINI_API_KEY")
print(f"KEY_LENGTH: {len(key) if key else 0}")
if key:
    print(f"KEY_START: {key[:10]}...")
