
from src.ledger_manager import LedgerManager
import json

lm = LedgerManager()
products = lm.get_recent_products(limit=10)
for p in products:
    print(f"ID: {p['id']}, Status: {p['status']}")
    if "20260220-211248" in p['id']:
        print(json.dumps(p, indent=2, ensure_ascii=False))
