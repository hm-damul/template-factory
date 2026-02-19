from src.ledger_manager import LedgerManager
import json

def check_promo_ready():
    lm = LedgerManager()
    waiting = lm.get_products_by_status("WAITING_FOR_PROMOTION")
    print(f"Total WAITING_FOR_PROMOTION: {len(waiting)}")
    
    # Check if they have promotion content
    count_with_content = 0
    from pathlib import Path
    for p in waiting:
        p_id = p['id']
        promo_dir = Path(f"outputs/{p_id}/promotions")
        if promo_dir.exists() and any(promo_dir.iterdir()):
            count_with_content += 1
            
    print(f"Products with generated promotion content: {count_with_content}")

if __name__ == "__main__":
    check_promo_ready()
