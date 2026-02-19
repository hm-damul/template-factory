import requests
import json
import sys

def check_url(url, name):
    try:
        print(f"Checking {name} at {url}...")
        resp = requests.get(url, timeout=5)
        print(f"{name} status code: {resp.status_code}")
        try:
            print(f"{name} response: {json.dumps(resp.json(), indent=2)}")
        except:
            print(f"{name} response text: {resp.text[:200]}")
    except Exception as e:
        print(f"Failed to check {name}: {e}")

if __name__ == "__main__":
    check_url("http://127.0.0.1:8099/api/system/status", "Dashboard Status")
    check_url("http://127.0.0.1:8099/api/products", "Dashboard Products")
    check_url("http://127.0.0.1:5000/health", "Payment Server")
    check_url("http://127.0.0.1:8088/health", "Preview Server")
