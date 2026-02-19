
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.append(str(PROJECT_ROOT))

from src.ledger_manager import LedgerManager
from src.config import Config
from src.publisher import Publisher

def retry_pending():
    lm = LedgerManager(Config.DATABASE_URL)
    pub = Publisher(lm)
    waiting = lm.get_products_by_status("WAITING_FOR_DEPLOYMENT")
    
    if not waiting:
        print("No products waiting for deployment.")
        return
        
    print(f"Found {len(waiting)} products waiting for deployment. Retrying...")
    for p in waiting:
        pid = p["id"]
        output_dir = PROJECT_ROOT / "outputs" / pid
        if output_dir.exists():
            print(f"Retrying deployment for {pid}...")
            res = pub.publish_product(pid, str(output_dir))
            print(f"Result for {pid}: {res.get('status')} - {res.get('error', '')}")

if __name__ == "__main__":
    retry_pending()
