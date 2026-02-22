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
    if sys.platform == "win32":
        subprocess.run("taskkill /F /IM python.exe", shell=True, capture_output=True)

    dashboard = start_process([sys.executable, "dashboard_server.py"], "Dashboard")
    preview = start_process([sys.executable, "preview_server.py"], "Preview")
    payment = start_process([sys.executable, "backend/payment_server.py"], "Payment")

    try:
        print("Waiting for servers...")
        time.sleep(5) 
        d_ok = check_url("http://127.0.0.1:8099/health")
        p_ok = check_url("http://127.0.0.1:8088/health")
        pay_ok = check_url("http://127.0.0.1:5000/health")
        
        results = []
        results.append(f"Dashboard (8099): {'OK' if d_ok else 'FAIL'}")
        results.append(f"Preview (8088): {'OK' if p_ok else 'FAIL'}")
        results.append(f"Payment (5000): {'OK' if pay_ok else 'FAIL'}")
        
        checkout_url = "http://127.0.0.1:8099/checkout/test-product"
        try:
            resp = requests.get(checkout_url, timeout=2)
            results.append(f"Checkout Route Test: Status {resp.status_code}")
        except Exception as e:
            results.append(f"Checkout Route Test: Failed ({e})")

        print("\n".join(results))
        with open("z_test_result.txt", "w") as f:
            f.write("\n".join(results))
            
    finally:
        dashboard.terminate()
        preview.terminate()
        payment.terminate()
        if sys.platform == "win32":
            subprocess.run("taskkill /F /IM python.exe", shell=True, capture_output=True)

if __name__ == "__main__":
    main()
