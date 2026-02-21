import requests
import sys

product_id = "20260220-211248-digital-asset-bundle-2026-02-2"

base_urls = [
    "https://metapassiveincome-final.vercel.app",
    "http://127.0.0.1:5000",
    "http://127.0.0.1:8099"
]

paths = [
    f"/outputs/{product_id}/index.html",
    f"/checkout/{product_id}",
    "/api/pay/health",
    "/",
    "/index.html"
]

for base_url in base_urls:
    print(f"\nChecking {base_url}...")
    for path in paths:
        # Dashboard handles checkout differently (via its own route)
        if base_url.endswith("8099") and path.startswith("/outputs/"):
             # Dashboard doesn't serve outputs directly unless proxied?
             # Actually dashboard_server.py serves templates, maybe not static outputs directly?
             # Let's check if it does.
             pass
        
        url = base_url + path
        try:
            r = requests.get(url, timeout=5)
            print(f"{path}: {r.status_code}")
            if r.status_code == 200:
                print(f"  Content snippet: {r.text[:100]}")
        except Exception as e:
            print(f"{path}: Error {e}")
