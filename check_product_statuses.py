from src.ledger_manager import LedgerManager
from src.config import Config
from collections import Counter

def check_statuses():
    ledger = LedgerManager(Config.DATABASE_URL)
    products = ledger.list_products()
    
    statuses = Counter(p.get("status") for p in products)
    print(f"Product Statuses: {statuses}")
    
    for p in products:
        if p.get("status") not in ["PUBLISHED", "SOLD"]:
            print(f"Non-published: {p.get('id')} ({p.get('status')})")

if __name__ == "__main__":
    check_statuses()
