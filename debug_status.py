from src.ledger_manager import LedgerManager

def check_statuses():
    lm = LedgerManager()
    products = lm.get_all_products()
    print(f"Total products: {len(products)}")
    
    status_counts = {}
    for p in products:
        s = p.get("status")
        status_counts[s] = status_counts.get(s, 0) + 1
        
        # Print a few examples of PROMOTED/PUBLISHED to check for whitespace or hidden chars
        if s in ["PROMOTED", "PUBLISHED"] and status_counts[s] <= 3:
            print(f"Product {p['id']} status: '{s}' (len: {len(s)})")

    print("Status distribution:")
    for s, c in status_counts.items():
        print(f"  '{s}': {c}")

if __name__ == "__main__":
    check_statuses()
