
import requests
import re

urls = [
    "https://meta-passive-income-20260215-014951-automated-crypto-a95e14yqh.vercel.app",
    "https://dev-best-pick-global.pantheonsite.io/2026/02/15/automated-crypto-tax-reporting-tool-2/"
]

for url in urls:
    print(f"Checking {url}...")
    try:
        r = requests.get(url, timeout=10)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            title_search = re.search(r'<title>(.*?)</title>', r.text, re.IGNORECASE)
            title = title_search.group(1) if title_search else "No Title"
            print(f"Title: {title}")
            if "Index of" in title or "Index of" in r.text[:500]:
                print("ISSUE: Directory Listing Detected")
            if "startPay" in r.text or "crypto-payment-widget" in r.text:
                print("Payment Widget: Found")
            else:
                print("Payment Widget: NOT Found (might be WP post)")
    except Exception as e:
        print(f"Error: {e}")
    print("-" * 20)
