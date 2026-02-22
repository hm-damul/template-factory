import requests
import sys

def check_status():
    try:
        print("Checking Dashboard Status...")
        resp = requests.get("http://127.0.0.1:8099/api/system/status", timeout=5)
        if resp.status_code == 200:
            print("Dashboard API Response:")
            print(resp.json())
        else:
            print(f"Dashboard API Error: {resp.status_code}")
    except Exception as e:
        print(f"Dashboard API Failed: {e}")

    try:
        print("\nChecking Preview Server...")
        resp = requests.get("http://127.0.0.1:8088/_list", timeout=5)
        print(f"Preview Server Status: {resp.status_code}")
    except Exception as e:
        print(f"Preview Server Failed: {e}")

    try:
        print("\nChecking Payment Server...")
        resp = requests.get("http://127.0.0.1:5000/health", timeout=5)
        print(f"Payment Server Status: {resp.status_code}")
        print(resp.json())
    except Exception as e:
        print(f"Payment Server Failed: {e}")

if __name__ == "__main__":
    check_status()
