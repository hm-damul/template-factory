
from src.ledger_manager import LedgerManager
import sys

lm = LedgerManager()
products = lm.list_products(limit=1000)
found = False
for p in products:
    if "014951" in p['id']:
        print(f"FOUND: {p['id']}, Status: {p['status']}")
        print(f"Deployment URL: {p.get('metadata', {}).get('deployment_url')}")
        found = True
        break

if not found:
    print("Product with '014951' not found.")
