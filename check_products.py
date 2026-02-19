from src.ledger_manager import LedgerManager
import sys

def main():
    try:
        lm = LedgerManager()
        prods = lm.list_products()
        if not prods:
            print("No products found.")
            return
        for p in prods:
            print(f"{p['id']}: {p['status']}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
