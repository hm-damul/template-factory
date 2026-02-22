import requests
import time

def check_url(url, description):
    try:
        print(f"Checking {description} at {url}...")
        response = requests.get(url, timeout=5)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("SUCCESS")
            return True
        else:
            print(f"FAILED with status {response.status_code}")
            return False
    except Exception as e:
        print(f"FAILED with error: {e}")
        return False

def main():
    print("Waiting for servers to initialize...")
    time.sleep(5)

    # 1. Check Dashboard Server Checkout Page
    dashboard_checkout_url = "http://127.0.0.1:8099/checkout/20260220-211248-digital-asset-bundle-2026-02-2"
    check_url(dashboard_checkout_url, "Dashboard Checkout Page")

    # 2. Check Preview Server
    preview_url = "http://127.0.0.1:8088/" # Might need a specific path, but root check confirms port open
    check_url(preview_url, "Preview Server")

    # 3. Check Payment Server
    payment_url = "http://127.0.0.1:5000/"
    check_url(payment_url, "Payment Server")

if __name__ == "__main__":
    main()
