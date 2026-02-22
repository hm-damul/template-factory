import requests
import sys
import time

product_id = "20260220-211248-digital-asset-bundle-2026-02-2"
vercel_base = "https://metapassiveincome-final.vercel.app"
local_dash = "http://127.0.0.1:8099"
local_api = "http://127.0.0.1:5000"

checks = [
    {
        "name": "Vercel Checkout Page",
        "url": f"{vercel_base}/checkout/{product_id}",
        "expect_status": 200,
        "expect_text": "Buy Direct"
    },
    {
        "name": "Vercel Output File",
        "url": f"{vercel_base}/outputs/{product_id}/index.html",
        "expect_status": 200,
        "expect_text": "Buy Direct"
    },
    {
        "name": "Local Dashboard Checkout",
        "url": f"{local_dash}/checkout/{product_id}",
        "expect_status": 200,
        "expect_text": "Buy Direct"  # Should be there if using same file
    },
    {
        "name": "Vercel Payment API Health",
        "url": f"{vercel_base}/api/pay/health",
        "expect_status": 200,
        "expect_text": "ok"
    }
]

print("Starting Verification...")
failed = False

for check in checks:
    print(f"\nChecking {check['name']} ({check['url']})...")
    try:
        r = requests.get(check['url'], timeout=10)
        print(f"Status: {r.status_code}")
        
        if r.status_code != check['expect_status']:
            print(f"FAIL: Expected {check['expect_status']}, got {r.status_code}")
            failed = True
            continue
            
        if check.get("expect_text"):
            if check["expect_text"] in r.text:
                print(f"PASS: Found '{check['expect_text']}'")
            else:
                print(f"FAIL: '{check['expect_text']}' not found in response")
                # print(f"Snippet: {r.text[:200]}...")
                failed = True
        else:
            print("PASS")
            
    except Exception as e:
        print(f"FAIL: Exception {e}")
        failed = True

if failed:
    print("\nVerification FAILED.")
    sys.exit(1)
else:
    print("\nVerification SUCCESS.")
    sys.exit(0)
