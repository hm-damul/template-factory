
import json
import re
from pathlib import Path
from payment_api import get_product_price_wei

def verify():
    root = Path("d:/auto/MetaPassiveIncome_FINAL")
    # Pick a random product that exists
    outputs = root / "outputs"
    products = [p for p in outputs.iterdir() if p.is_dir()]
    if not products:
        print("No products found")
        return

    # Sort by time to get recent
    products.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    
    target = products[0]
    pid = target.name
    
    print(f"Checking product: {pid}")
    
    # 1. Check schema file directly
    schema_path = target / "product_schema.json"
    if schema_path.exists():
        data = json.loads(schema_path.read_text(encoding="utf-8"))
        print(f"Schema price (raw): {data.get('_injected_price')}")
        print(f"Schema section price: {data.get('sections', {}).get('pricing', {}).get('price')}")
    
    # 2. Check calculated WEI
    wei = get_product_price_wei(root, pid)
    eth = wei / 1e18
    print(f"Calculated WEI: {wei}")
    print(f"Calculated ETH: {eth:.6f}")
    
    expected_eth = 0.0236 # $59 * 0.0004
    if abs(eth - expected_eth) < 0.001:
        print("PASS: Price matches $59 target")
    else:
        print(f"FAIL: Price mismatch. Expected ~{expected_eth}, got {eth}")

if __name__ == "__main__":
    verify()
