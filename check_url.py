import requests
try:
    url = "https://metapassiveincome-final.vercel.app/checkout/20260220-211248-digital-asset-bundle-2026-02-2"
    response = requests.head(url)
    print(f"URL: {url}")
    print(f"Status: {response.status_code}")
    if response.status_code == 404:
        # Try root to see if deployment is up at all
        root_resp = requests.head("https://metapassiveincome-final.vercel.app/")
        print(f"Root Status: {root_resp.status_code}")
        
        # Try direct path
        direct_url = "https://metapassiveincome-final.vercel.app/outputs/20260220-211248-digital-asset-bundle-2026-02-2/index.html"
        direct_resp = requests.head(direct_url)
        print(f"Direct URL Status: {direct_resp.status_code}")
except Exception as e:
    print(f"Error: {e}")
