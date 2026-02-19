
from src.ledger_manager import LedgerManager
import os
from pathlib import Path

def check_waiting_products():
    lm = LedgerManager()
    waiting = lm.get_products_by_status("WAITING_FOR_DEPLOYMENT")
    print(f"Products waiting for deployment: {len(waiting)}")
    
    # Check if any have promotions generated already
    with_promotions = 0
    for p in waiting:
        p_dir = Path(f"outputs/{p['id']}")
        if (p_dir / "promotions").exists():
            with_promotions += 1
            
    print(f"Waiting products with promotions folder: {with_promotions}")

if __name__ == "__main__":
    check_waiting_products()
