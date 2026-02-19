import sys
import os
sys.path.append(os.getcwd())
from src.ledger_manager import LedgerManager

def recover():
    lm = LedgerManager()
    products = lm.get_all_products()
    count = 0
    print("Starting recovery for DEPLOYMENT_FAILED products...")
    for p in products:
        if p["status"] == "READY_TO_PUBLISH":
            print(f"Resetting {p['id']} to READY_TO_PACKAGE")
            lm.update_product_status(p["id"], "READY_TO_PACKAGE")
            count += 1
    
    print(f"========================================")
    print(f"Reset {count} products to READY_TO_PACKAGE (to force payment injection).")

if __name__ == "__main__":
    recover()