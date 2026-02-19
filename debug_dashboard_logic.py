from src.ledger_manager import LedgerManager
import json

def check_one_product():
    lm = LedgerManager()
    products = lm.get_all_products()
    promoted = [p for p in products if p['status'] == 'PROMOTED']
    if promoted:
        p = promoted[0]
        print(f"Product: {p['id']}")
        print(f"Status: '{p['status']}'")
        print(f"Metadata price: {p['metadata'].get('price_usd')}")
        
        # Simulate dashboard logic
        qa_status = "Pending"
        if p.get("status") == "PUBLISHED":
            qa_status = "Passed"
        elif p.get("status") == "PROMOTED":
            qa_status = "Published & Promoted"
        
        print(f"Calculated qa_status: '{qa_status}'")
    else:
        print("No PROMOTED products found.")

if __name__ == "__main__":
    check_one_product()
