
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.append(str(PROJECT_ROOT))

from src.ledger_manager import LedgerManager
from src.config import Config

def force_redeploy():
    lm = LedgerManager(Config.DATABASE_URL)
    products = lm.get_all_products()
    
    count = 0
    for p in products:
        pid = p['id']
        # Set status to WAITING_FOR_DEPLOYMENT
        # But verify if product folder exists
        if (PROJECT_ROOT / "outputs" / pid).exists():
            lm.update_product_status(pid, "WAITING_FOR_DEPLOYMENT")
            print(f"[{pid}] Status set to WAITING_FOR_DEPLOYMENT")
            count += 1
            
    print(f"Updated {count} products to WAITING_FOR_DEPLOYMENT.")

if __name__ == "__main__":
    force_redeploy()
