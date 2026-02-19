import requests

urls = [
    "https://meta-passive-income-20260215-212725-token-gated-cont-b5yvitb8a.vercel.app",
    "https://meta-passive-income-20260215-212725-token-gated-cont-c4yhea4vn.vercel.app"
]

for base in urls:
    print(f"Checking {base}")
    
    # Check Debug
    u = f"{base}/api/pay/debug"
    try:
        r = requests.get(u, timeout=5)
        print(f"DEBUG Status: {r.status_code}")
        print(f"DEBUG Content-Type: {r.headers.get('Content-Type')}")
        print(f"DEBUG Body start: {r.text[:100]}")
    except Exception as e:
        print(f"DEBUG Error: {e}")
        
    # Check Start
    u = f"{base}/api/pay/start"
    payload = {
        "product_id": "test_product_123",
        "amount": 50,
        "currency": "USD",
        "provider": "simulated"
    }
    try:
        r = requests.post(u, json=payload, timeout=5)
        print(f"START Status: {r.status_code}")
        print(f"START Content-Type: {r.headers.get('Content-Type')}")
        print(f"START Body start: {r.text[:100]}")
    except Exception as e:
        print(f"START Error: {e}")
        
    # Check Download
    token = "b3JkXzdiMzY3ODgzNGUxZGRhMjN8dGVzdC1wcm9kfDE3NzEyMzY5MzV8MjQwNWVhMjc2ZDllNzk5YXwxfGFadnZtOEhEN21lMXdqd2U0VkZaaWdRTUZmOFh6SFh4MF9mdk5fTldIRWc"
    u = f"{base}/api/pay/download?token={token}"
    try:
        r = requests.get(u, timeout=5)
        print(f"DOWNLOAD Status: {r.status_code}")
        print(f"DOWNLOAD Content-Type: {r.headers.get('Content-Type')}")
        print(f"DOWNLOAD Body start: {r.text[:100]}")
    except Exception as e:
        print(f"DOWNLOAD Error: {e}")
        
    print("-" * 20)
