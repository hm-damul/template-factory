
import sys
from pathlib import Path
import json

# Add src to path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from src.ledger_manager import LedgerManager
from src.config import Config

def check_product(product_id):
    ledger = LedgerManager(Config.DATABASE_URL)
    product = ledger.get_product(product_id)
    
    if not product:
        print(f"Product {product_id} not found in ledger.")
        return
        
    print(f"Product: {product['id']}")
    print(f"Status: {product['status']}")
    
    meta = product.get("metadata", {})
    if isinstance(meta, str):
        meta = json.loads(meta)
        
    print("Metadata:")
    print(json.dumps(meta, indent=2))

if __name__ == "__main__":
    check_product("20260220-211248-digital-asset-bundle-2026-02-2")
