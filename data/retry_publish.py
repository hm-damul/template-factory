# -*- coding: utf-8 -*-
import sys
import os
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from promotion_dispatcher import dispatch_publish

product_id = "20260215-014951-automated-crypto-tax-reporting"

print(f"Republishing {product_id} to WordPress...")
try:
    results = dispatch_publish(product_id, channels=["wordpress"])
    print("Publish results:", results)
except Exception as e:
    print(f"Publish failed: {e}")
