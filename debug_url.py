
import requests
import sys

url = "https://metapassiveincome-final.vercel.app/outputs/20260220-023210-digital-products-goldmine-200/index.html"

print(f"Checking URL: {url}")
try:
    r = requests.get(url, timeout=15)
    print(f"Status Code: {r.status_code}")
    print(f"Headers: {r.headers}")
    print(f"Content Preview: {r.text[:200]}")
except Exception as e:
    print(f"Error: {e}")
