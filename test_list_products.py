
import os
import sys
from pathlib import Path
import time
import json

PROJECT_ROOT = Path(r"d:\auto\MetaPassiveIncome_FINAL")
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard_server import _list_products

def test():
    print("Testing _list_products()...")
    products = _list_products()
    print(f"Found {len(products)} products.")
    for p in products:
        print(f"- {p['product_id']}: status={p['status']}, has_landing={p['has_landing']}")

if __name__ == "__main__":
    test()
