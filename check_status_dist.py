
from src.ledger_manager import LedgerManager
from collections import Counter

def check_status_distribution():
    lm = LedgerManager()
    with lm.Session() as session:
        from src.ledger_manager import Product
        products = session.query(Product).all()
        statuses = [p.status for p in products]
        dist = Counter(statuses)
        print("Status Distribution:")
        for status, count in dist.items():
            print(f"  {status}: {count}")

if __name__ == "__main__":
    check_status_distribution()
