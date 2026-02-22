import requests
import socket
import time
import sys

def check_port(port, retries=3):
    for i in range(retries):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        if result == 0:
            return True
        time.sleep(1)
    return False

def check_url(url, description, retries=3):
    for i in range(retries):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"[OK] {description}: {response.status_code}")
                return True
            else:
                print(f"[WARN] {description}: {response.status_code} (Retry {i+1}/{retries})")
        except Exception as e:
            # Only print error on last retry
            if i == retries - 1:
                print(f"[FAIL] {description}: {str(e)}")
        time.sleep(1)
    return False

print("--- System Health Check ---")

servers = {
    8099: "Dashboard Server",
    8088: "Preview Server",
    5000: "Payment Server"
}

all_ok = True

for port, name in servers.items():
    if check_port(port):
        print(f"[OK] {name} is listening on port {port}")
    else:
        print(f"[FAIL] {name} is NOT listening on port {port}")
        all_ok = False

print("\n--- URL Checks ---")
if not check_url("http://127.0.0.1:8099/", "Dashboard Home"): all_ok = False
if not check_url("http://127.0.0.1:8088/_list", "Preview List"): all_ok = False
if not check_url("http://127.0.0.1:5000/health", "Payment Health"): all_ok = False

target_product = "20260220-211248-digital-asset-bundle-2026-02-2"
print(f"\n--- Target Product Checks: {target_product} ---")
if not check_url(f"http://127.0.0.1:8099/checkout/{target_product}", "Dashboard Checkout Page"): all_ok = False
if not check_url(f"http://127.0.0.1:8088/outputs/{target_product}/index.html", "Preview Page (via /outputs path)"): all_ok = False
# The preview server also serves from root for product_id
# check_url(f"http://127.0.0.1:8088/{target_product}/index.html", "Preview Page (via root path)")

if all_ok:
    print("\n[SUCCESS] All systems operational.")
    sys.exit(0)
else:
    print("\n[FAILURE] Some systems are not responding.")
    sys.exit(1)
