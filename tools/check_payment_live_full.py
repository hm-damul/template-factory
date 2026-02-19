import requests
import sys

# URLs of the Vercel deployment
url_bases = [
    "https://meta-passive-income-20260215-212725-token-gated-cont-c4yhea4vn.vercel.app"
]

def check(base_url, endpoint, params=None, method="GET", json_data=None):
    url = f"{base_url}{endpoint}"
    print(f"Checking {url}...")
    try:
        if method == "GET":
            r = requests.get(url, params=params, timeout=10)
        else:
            r = requests.post(url, json=json_data, timeout=10)
            
        print(f"Status: {r.status_code}")
        print("Body start:")
        print(r.text[:500])
        print("Body end")
        return r
    except Exception as e:
        print(f"Error: {e}")
        return None

for base in url_bases:
    print(f"\n--- Checking Base: {base} ---")
    
    # 1. Start Payment
    print("\n[Step 1] Start Payment")
    r_start = check(base, "/api/pay/start", method="POST", json_data={
        "product_id": "test-prod",
        "amount": 10,
        "currency": "usd",
        "provider": "simulated"
    })
    
    order_id = None
    if r_start and r_start.status_code == 200:
        try:
            data = r_start.json()
            order_id = data.get("order_id")
            print(f"Created Order ID: {order_id}")
        except:
            print("Failed to parse start response")
            
    # 2. Check Payment
    if order_id:
        print("\n[Step 2] Check Payment (Pending)")
        check(base, "/api/pay/check", params={"order_id": order_id})
        
        print("\n[Step 2.1] Waiting 4 seconds for simulated payment completion...")
        import time
        time.sleep(4)
        
        print("\n[Step 2.2] Check Payment (Should be Paid)")
        r_paid = check(base, "/api/pay/check", params={"order_id": order_id})
        if r_paid and r_paid.status_code == 200:
            d = r_paid.json()
            status = d.get("status")
            dl = d.get("download_url")
            print(f"Final Status: {status}")
            print(f"Download URL: {dl}")
            if status == "paid" and dl:
                print("SUCCESS: Payment flow verified!")
            else:
                print("FAILURE: Payment flow failed!")
    else:
        print("Skipping check as start failed")

    # 3. Debug info
    print("\n[Step 3] Debug Info")
    check(base, "/api/pay/debug")
