
import requests
import sys

url = "https://meta-passive-income-20260214-105333-global-merchant-mjz1ndabf.vercel.app"
try:
    r = requests.get(url, timeout=10)
    print(f"Status: {r.status_code}")
    if "Why Choose Us" in r.text:
        print("SUCCESS: Comparison table found.")
    else:
        print("FAIL: Comparison table NOT found.")
        
    if 'data-price="' in r.text:
        print("SUCCESS: data-price attribute found.")
    else:
        print("FAIL: data-price attribute NOT found.")
        
    # Check for specific price
    if '$29.0' in r.text or '$29.00' in r.text:
         print("SUCCESS: Price $29.0 found.")
    else:
         print("CHECK: Price might be different or dynamic.")
         
except Exception as e:
    print(f"Error: {e}")
