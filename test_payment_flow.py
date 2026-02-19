
import requests
import json
import time

def test_flow():
    base_url = "http://127.0.0.1:5000"
    product_id = "20260208-095133-온라인-강의-디지털-상품-판매-페이지"
    
    print(f"1. Starting payment for {product_id}...")
    try:
        res = requests.post(f"{base_url}/api/pay/start", json={
            "product_id": product_id,
            "price_amount": 19,
            "price_currency": "usd"
        })
        res.raise_for_status()
        data = res.json()
        print("Response:", json.dumps(data, indent=2, ensure_ascii=False))
        
        order_id = data.get("order_id")
        download_url = data.get("download_url")
        token = data.get("token")
        
        if not order_id or not download_url:
            print("FAILED: Missing order_id or download_url")
            return

        print(f"\n2. Checking payment status for {order_id}...")
        res = requests.get(f"{base_url}/api/pay/check?order_id={order_id}")
        print("Status:", res.json())

        print(f"\n3. Attempting download from {download_url}...")
        # download_url is relative, e.g., /api/pay/download?...
        full_download_url = base_url + download_url
        res = requests.get(full_download_url)
        print("Download Result Status:", res.status_code)
        if res.status_code == 200:
            print("Download Header:", res.headers.get("Content-Disposition"))
            content_len = len(res.content)
            print(f"Downloaded content size: {content_len} bytes")
        else:
            print("Download FAILED")

        print("\n4. Verifying token reissue...")
        res = requests.get(f"{base_url}/api/pay/token?order_id={order_id}")
        print("Token Reissue:", res.json())

    except Exception as e:
        print(f"Error during test: {e}")

if __name__ == "__main__":
    test_flow()
