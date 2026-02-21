import requests
import sys

base_urls = [
    "https://metapassiveincome-final.vercel.app",
    "http://localhost:5000"
]
product_id = "20260220-211248-digital-asset-bundle-2026-02-2"
paths = [
    f"/outputs/{product_id}/index.html",
    "/api/pay/health",
    "/",
    "/index.html"
]

for base_url in base_urls:
    print(f"\nChecking {base_url}...")
    for path in paths:
        url = base_url + path
        try:
            r = requests.get(url, timeout=5)
            print(f"{path}: {r.status_code}")
            if r.status_code == 200:
                print(f"  Content snippet: {r.text[:100]}")
        except Exception as e:
            print(f"{path}: Error {e}")
