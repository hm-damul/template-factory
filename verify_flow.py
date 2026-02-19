
import requests
import time
import json

def verify_payment_flow():
    print("--- Starting End-to-End Payment Flow Verification ---")
    
    # 1. Start Payment (Lead Capture included)
    product_id = "test-crypto-landing-page-001"
    email = "test_user@example.com"
    plan = "Pro"
    price = "$49"
    
    print(f"\n[Step 1] Starting payment for {product_id} (Plan: {plan}, Email: {email})...")
    start_url = f"http://127.0.0.1:5000/api/pay/start"
    payload = {
        "product_id": product_id,
        "lead_email": email,
        "plan": plan,
        "price": price
    }
    
    try:
        resp = requests.post(start_url, json=payload, timeout=5)
        print(f"Response Status: {resp.status_code}")
        data = resp.json()
        print(f"Response Data: {json.dumps(data, indent=2)}")
        
        if resp.status_code != 200 or "order_id" not in data:
            print("FAILED: Could not create order.")
            return
        
        order_id = data["order_id"]
        print(f"Order ID created: {order_id}")
        
    except Exception as e:
        print(f"ERROR during start: {e}")
        return

    # 2. Check Payment Status
    print(f"\n[Step 2] Checking payment status for Order {order_id}...")
    check_url = f"http://127.0.0.1:5000/api/pay/check?order_id={order_id}&product_id={product_id}"
    
    try:
        resp = requests.get(check_url, timeout=5)
        data = resp.json()
        status = data.get('status')
        print(f"Status check response: {status}")
        
        # 3. Mark as Paid (if not already)
        if status != "paid":
            print(f"\n[Step 3] Marking order {order_id} as PAID (test-only via Dashboard)...")
            # The route /action/mark_paid in dashboard_server.py is POST
            mark_url = f"http://127.0.0.1:8099/action/mark_paid"
            resp = requests.post(mark_url, data={"order_id": order_id}, timeout=5)
            if resp.status_code in [200, 302]:
                print("Order marked as paid successfully.")
            else:
                print(f"FAILED to mark as paid: {resp.status_code}")
                return
        else:
            print("\n[Step 3] Skipping mark-as-paid (already paid).")

        # 4. Verify status is now 'paid' and get download URL
        print(f"\n[Step 4] Final status check for Order {order_id}...")
        resp = requests.get(check_url, timeout=5)
        data = resp.json()
        status = data.get("status")
        download_url = data.get("download_url")
        print(f"Status: {status}, Download URL: {download_url}")
        
        if status != "paid" or not download_url:
            print("FAILED: Order not ready for download.")
            return

        # 5. Download via Proxy (Dashboard Server)
        # download_url is relative to the payment server, e.g., "/api/pay/download?..."
        proxy_download_url = f"http://127.0.0.1:8099{download_url}"
        print(f"\n[Step 5] Attempting download via Dashboard Proxy: {proxy_download_url}")
        
        resp = requests.get(proxy_download_url, stream=True, timeout=10)
        print(f"Proxy Download Status: {resp.status_code}")
        
        if resp.status_code == 200:
            content_type = resp.headers.get('Content-Type')
            content_length = resp.headers.get('Content-Length')
            print(f"Download SUCCESS! Content-Type: {content_type}, Length: {content_length}")
            
            # Save a small chunk to verify
            with open("verified_download.zip", "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        break # Just one chunk is enough for verification
            print("Verified download chunk saved to verified_download.zip")
        else:
            print(f"FAILED: Proxy download returned {resp.status_code}")
            print(f"Error Message: {resp.text}")

    except Exception as e:
        print(f"ERROR during verification: {e}")

if __name__ == "__main__":
    verify_payment_flow()
