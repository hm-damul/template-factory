import requests
import sys

# URLs of the Vercel deployment
url_bases = [
    "https://meta-passive-income-20260215-212725-token-gated-cont-mxvro821q.vercel.app"
]

def check(base_url, endpoint, params=None):
    url = f"{base_url}{endpoint}"
    print(f"Checking {url}...")
    try:
        r = requests.get(url, params=params, timeout=10)
        print(f"Status: {r.status_code}")
        print("Body start:")
        print(r.text[:500])
        print("Body end")
        return r.status_code
    except Exception as e:
        print(f"Error: {e}")
        return None

for base in url_bases:
    print(f"\n--- Checking Base: {base} ---")
    check(base, "/api/pay/check", {"order_id": "test", "product_id": "test"})
    check(base, "/api/pay/debug")
    check(base, "/api/health")
