
import requests
import time
import sys
import json

BASE_URL = "https://meta-passive-income-20260215-212725-token-gated-cont-pv3j7zh9o.vercel.app"

def run_verification():
    print(f"Target: {BASE_URL}")

    # 0. Check Health (loop until ready)
    print("\n[0] Checking Health (waiting for deployment)...")
    for i in range(30):
        try:
            r = requests.get(f"{BASE_URL}/api/health", timeout=10)
            if r.status_code == 200 and "application/json" in r.headers.get("Content-Type", ""):
                print(f"   Health OK! Body: {r.text[:100]}")
                break
            else:
                print(f"   [{i+1}/30] Waiting... (Status: {r.status_code}, Type: {r.headers.get('Content-Type')})")
        except Exception as e:
            print(f"   [{i+1}/30] Error: {e}")
        time.sleep(5)
    else:
        print("   TIMEOUT: Deployment not ready.")
        return

    # 0.1 Check Debug
    print("\n[0.1] Checking Debug...")
    try:
        r = requests.get(f"{BASE_URL}/api/pay/debug", timeout=10)
        print(f"   Status: {r.status_code}")
        print(f"   Body: {r.text[:500]}")
    except Exception as e:
        print(f"   FAILED to check debug: {e}")
    
    # 1. Start Payment
    print("\n[1] Starting Payment...")
    try:
        r = requests.post(f"{BASE_URL}/api/pay/start", json={
            "product_id": "test-prod-123",
            "amount": 10,
            "currency": "usd",
            "provider": "simulated"
        }, timeout=10)
        try:
            data = r.json()
        except ValueError:
            print(f"   ERROR: Non-JSON response (status {r.status_code}):")
            print(r.text[:500])
            return

        order_id = data.get("order_id")
        print(f"   Order ID: {order_id}")
        print(f"   Status: {data.get('status')}")
    except Exception as e:
        print(f"   FAILED to start payment: {e}")
        return

    # 2. Check (should be pending)
    print("\n[2] Checking initial status...")
    try:
        r = requests.get(f"{BASE_URL}/api/pay/check", params={"order_id": order_id}, timeout=10)
        data = r.json()
        print(f"   Status: {data.get('status')}")
    except Exception as e:
        print(f"   FAILED to check status: {e}")

    # 3. Wait for auto-completion
    print("\n[3] Waiting 4 seconds for simulated payment...")
    time.sleep(4)

    # 4. Check (should be paid)
    print("\n[4] Checking final status...")
    download_url = None
    try:
        r = requests.get(f"{BASE_URL}/api/pay/check", params={"order_id": order_id}, timeout=10)
        data = r.json()
        status = data.get("status")
        download_url = data.get("download_url")
        print(f"   Status: {status}")
        print(f"   Download URL: {download_url}")
        
        if status != "paid":
            print("   FAILURE: Status is not paid")
            return
        if not download_url:
            print("   FAILURE: No download URL")
            return
    except Exception as e:
        print(f"   FAILED to check final status: {e}")
        return

    # 5. Download file
    print("\n[5] Attempting download...")
    full_dl_url = f"{BASE_URL}{download_url}"
    print(f"   URL: {full_dl_url}")
    try:
        r = requests.get(full_dl_url, timeout=30)
        print(f"   HTTP Status: {r.status_code}")
        if r.status_code == 200:
            print(f"   Content-Type: {r.headers.get('Content-Type')}")
            print(f"   Content-Length: {len(r.content)} bytes")
            if len(r.content) > 0:
                print("   SUCCESS: File downloaded successfully!")
            else:
                print("   WARNING: File empty")
        else:
            print(f"   FAILURE: Download failed with status {r.status_code}")
            print(f"   Response: {r.text[:200]}")
    except Exception as e:
        print(f"   FAILED to download: {e}")

if __name__ == "__main__":
    run_verification()
