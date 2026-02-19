
import requests
try:
    r = requests.get("https://dev-best-pick-global.pantheonsite.io/", timeout=10)
    print(f"WP Status: {r.status_code}")
except Exception as e:
    print(f"WP Error: {e}")
