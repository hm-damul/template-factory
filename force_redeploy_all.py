from src.auto_heal_system import AutoHealSystem
from src.ledger_manager import LedgerManager
from src.config import Config
import logging
import sys
import time

def force_redeploy_all():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    logger = logging.getLogger("ForceRedeploy")
    
    ahs = AutoHealSystem()
    ledger = LedgerManager(Config.DATABASE_URL)
    products = ledger.list_products()
    
    logger.info(f"Found {len(products)} products. Starting forced redeployment...")
    
    count = 0
    for p in products:
        pid = p.get("id")
        status = p.get("status")
        
        if status == "PUBLISHED":
            logger.info(f"[{count+1}] Redeploying {pid}...")
            try:
                ahs._redeploy_product(pid)
                logger.info(f"Redeployed {pid}")
                time.sleep(2) # Avoid rate limits
                count += 1
            except Exception as e:
                logger.error(f"Failed to redeploy {pid}: {e}")
                
    logger.info(f"Total redeployed: {count}")

if __name__ == "__main__":
    force_redeploy_all()
