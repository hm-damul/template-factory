
import sys

def check_import(name):
    try:
        __import__(name)
        print(f"{name}: OK")
    except ImportError as e:
        print(f"{name}: FAIL - {e}")

print("Checking critical dependencies...")
check_import("flask")
check_import("flask_cors")
check_import("requests")
check_import("google.genai")
# check_import("google.generativeai") # Legacy, optional
check_import("moviepy")
check_import("decorator")
check_import("sqlalchemy")
check_import("tweepy")
print("Done.")
