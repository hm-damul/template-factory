import requests
import sys
import time

def check_url(url, name):
    try:
        r = requests.get(url, timeout=2)
        print(f"[{name}] Status: {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"[{name}] Failed: {e}")
        return False

def check_imports():
    print("\nChecking imports...")
    try:
        import praw
        print("[Import] praw: OK")
    except ImportError as e:
        print(f"[Import] praw: FAILED ({e})")

    try:
        import google.genai
        print("[Import] google.genai: OK")
    except ImportError as e:
        print(f"[Import] google.genai: FAILED ({e})")
        
    try:
        import decorator
        print("[Import] decorator: OK")
    except ImportError as e:
        print(f"[Import] decorator: FAILED ({e})")

print("Waiting for services to start (10s)...")
time.sleep(10)

print("\nChecking Services...")
check_url("http://127.0.0.1:8099/health", "Dashboard")
check_url("http://127.0.0.1:5000/health", "Payment Server")
    check_url("http://127.0.0.1:8088/health", "Preview Server")

check_imports()
