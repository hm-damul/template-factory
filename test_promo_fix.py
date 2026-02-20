
import sys
import json
from pathlib import Path
import re

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

from promotion_dispatcher import build_channel_payloads

product_id = "20260220-113551-top-definition-meaning"
print(f"Regenerating promotions for {product_id}...")

payloads = build_channel_payloads(product_id)

blog_html = payloads.get("blog", {}).get("html", "")
print(f"Generated HTML length: {len(blog_html)}")

# Check for price in HTML
price_match = re.search(r'\$49\.00', blog_html)
if price_match:
    print("SUCCESS: Found $49.00 in HTML")
else:
    print("FAILURE: Did not find $49.00 in HTML")
    # Find what price IS there
    found_prices = re.findall(r'\$\d+\.\d{2}', blog_html)
    print(f"Found prices: {found_prices}")

# Check Market Analysis Table
if "Market Price Analysis" in blog_html:
    print("SUCCESS: Found Market Price Analysis section")
else:
    print("FAILURE: Market Price Analysis section missing")
