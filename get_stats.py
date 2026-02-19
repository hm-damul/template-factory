from src.ledger_manager import LedgerManager
import json

def get_stats():
    lm = LedgerManager()
    prods = lm.list_products(limit=1000)
    stats = {}
    for p in prods:
        s = p.get('status')
        stats[s] = stats.get(s, 0) + 1
    print(json.dumps(stats, indent=2))

if __name__ == "__main__":
    get_stats()
