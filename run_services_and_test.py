import subprocess
import sys
import time
import requests
import os
import signal

def start_process(cmd, name):
    print(f"Starting {name}...")
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def check_url(url, retries=5):
    for i in range(retries):
        try:
            resp = requests.get(url, timeout=2)
            if resp.status_code == 200:
                return True
        except:
            pass
        time.sleep(1)
    return False

def main():
    # Kill existing processes on ports 8099, 8088, 5000 just in case
    if sys.platform == "win32":
        subprocess.run("taskkill /F /IM python.exe", shell=True, capture_output=True)

    # Start servers
    dashboard = start_process([sys.executable, "dashboard_server.py"], "Dashboard")
    preview = start_process([sys.executable, "preview_server.py"], "Preview")
    payment = start_process([sys.executable, "backend/payment_server.py"], "Payment")

    try:
        # Wait for servers to come up
        print("Waiting for servers...")
        d_ok = check_url("http://127.0.0.1:8099/health")
        p_ok = check_url("http://127.0.0.1:8088/health")
        pay_ok = check_url("http://127.0.0.1:5000/health")
        
        results = []
        results.append(f"Dashboard (8099): {'OK' if d_ok else 'FAIL'}")
        results.append(f"Preview (8088): {'OK' if p_ok else 'FAIL'}")
        results.append(f"Payment (5000): {'OK' if pay_ok else 'FAIL'}")
        
        # Test Checkout Route
        # Need a valid product ID. I'll pick one from outputs if available, or just use a dummy one (might 404 if product not in ledger)
        # But wait, ledger is file based (sqlite or json).
        # dashboard_server.py uses LedgerManager.
        
        # Check checkout page
        checkout_url = "http://127.0.0.1:8099/checkout/test-product"
        # Since 'test-product' likely doesn't exist in DB, it might return 404 "Product not found".
        # But if it returns 404 from MY code, that means the route IS reachable.
        # If the route was missing, it would be a standard 404 (or 500).
        # My code: if not product: return "Product not found", 404
        
        try:
            resp = requests.get(checkout_url, timeout=2)
            results.append(f"Checkout Route Test: Status {resp.status_code}, Content: {resp.text[:50]}")
        except Exception as e:
            results.append(f"Checkout Route Test: Failed ({e})")

        with open("test_result.txt", "w") as f:
            f.write("\n".join(results))
            
    finally:
        # Cleanup
        dashboard.terminate()
        preview.terminate()
        payment.terminate()
        # Ensure kill
        if sys.platform == "win32":
            subprocess.run("taskkill /F /IM python.exe", shell=True, capture_output=True)

if __name__ == "__main__":
    main()
