
from src.ledger_manager import LedgerManager
import json

lm = LedgerManager()
products = lm.list_products(limit=10)
for p in products:
    print(f"ID: {p['id']}, Status: {p['status']}, URL: {p.get('metadata', {}).get('deployment_url')}")
