
import json
import os
import sys
sys.path.append(os.getcwd())
from src.ledger_manager import LedgerManager
from src.config import Config

def check_status():
    lm = LedgerManager(Config.DATABASE_URL)
    products = lm.list_products()
    stats = {}
    for p in products:
        status = p['status']
        stats[status] = stats.get(status, 0) + 1
    print(json.dumps(stats, indent=2))
    
    # Also list products in non-PROMOTED status
    others = [p for p in products if p['status'] != 'PROMOTED']
    if others:
        print("\nNon-PROMOTED Products:")
        for p in others:
            print(f"- {p['id']}: {p['status']}")

if __name__ == "__main__":
    check_status()
