import requests
try:
    resp = requests.get('http://127.0.0.1:8099/api/system/progress')
    print(resp.json())
except Exception as e:
    print(f"Error: {e}")
