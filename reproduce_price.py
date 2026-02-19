
import json
import re
import os
from pathlib import Path

def get_product_price_wei_test(project_root: Path, product_id: str) -> int:
    # Mocking get_evm_config
    default_wei = 10000000000000000 # 0.01 ETH
    
    product_dir = project_root / "outputs" / product_id
    
    print(f"Checking {product_dir}")
    
    # 1. product_schema.json
    schema_path = product_dir / "product_schema.json"
    if schema_path.exists():
        try:
            content = schema_path.read_text(encoding="utf-8")
            schema = json.loads(content)
            price_str = schema.get("sections", {}).get("pricing", {}).get("price", "")
            print(f"Schema price_str: '{price_str}'")
            if price_str:
                price_val = float(re.sub(r'[^\d.]', '', price_str))
                print(f"Parsed price_val: {price_val}")
                wei = int(price_val * 4 * 1e14)
                print(f"Calculated Wei: {wei}")
                return wei
        except Exception as e:
            print(f"Schema error: {e}")
            pass

    # 2. manifest.json
    manifest_path = product_dir / "manifest.json"
    if manifest_path.exists():
        try:
            m = json.loads(manifest_path.read_text(encoding="utf-8"))
            price_usd = m.get("price_usd")
            print(f"Manifest price_usd: {price_usd}")
            if price_usd:
                wei = int(float(price_usd) * 4 * 1e14)
                print(f"Manifest Wei: {wei}")
                return wei
        except Exception as e:
            print(f"Manifest error: {e}")
            pass

    return default_wei

if __name__ == "__main__":
    root = Path("d:/auto/MetaPassiveIncome_FINAL")
    pid = "20260214-231100-unknown-single"
    wei = get_product_price_wei_test(root, pid)
    print(f"Final Wei: {wei}")
    print(f"Final ETH: {wei / 1e18}")
