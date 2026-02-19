
import sys
import os

try:
    import requests
    print("requests: OK")
except ImportError:
    print("requests: MISSING")

try:
    import jwt
    print("PyJWT: OK")
except ImportError:
    print("PyJWT: MISSING")

try:
    from dotenv import load_dotenv
    print("python-dotenv: OK")
except ImportError:
    print("python-dotenv: MISSING")

print(f"Python version: {sys.version}")
print(f"CWD: {os.getcwd()}")
