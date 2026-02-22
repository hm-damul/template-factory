import requests
import time
import sys

url = "https://metapassiveincome-final.vercel.app/checkout/20260220-211248-digital-asset-bundle-2026-02-2/index.html"
# Also check without index.html just in case of rewrite rules
url_rewrite = "https://metapassiveincome-final.vercel.app/checkout/20260220-211248-digital-asset-bundle-2026-02-2"

print(f"Checking URL: {url}")
for i in range(10):
    try:
        r = requests.head(url)
        print(f"Attempt {i+1}: {r.status_code}")
        if r.status_code == 200:
            print("SUCCESS: URL is accessible.")
            break
        
        r2 = requests.head(url_rewrite)
        print(f"Attempt {i+1} (rewrite): {r2.status_code}")
        if r2.status_code == 200:
             print("SUCCESS: Rewrite URL is accessible.")
             break
    except Exception as e:
        print(f"Error: {e}")
    time.sleep(5)
