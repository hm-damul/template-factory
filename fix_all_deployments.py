import sys
import os
import time
import logging
import json
from src.auto_heal_system import AutoHealSystem
from src.ledger_manager import LedgerManager
from src.config import Config

def fix_all_deployments():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    logger = logging.getLogger("FixDeployments")
    
    ahs = AutoHealSystem()
    ledger = LedgerManager(Config.DATABASE_URL)
    products = ledger.list_products()
    
    logger.info(f"Found {len(products)} products. Starting fix for all deployed products...")
    
    count = 0
    for p in products:
        pid = p.get("id")
        status = p.get("status")
        meta = p.get("metadata") or {}
        if isinstance(meta, str):
            meta = json.loads(meta)
            
        url = meta.get("deployment_url")
        
        # Redeploy if it has a URL OR if status suggests it should be deployed
        should_redeploy = False
        if url:
            should_redeploy = True
        elif status in ["PUBLISHED", "PROMOTED", "WAITING_FOR_DEPLOYMENT"]:
            should_redeploy = True
            
        if should_redeploy:
            logger.info(f"[{count+1}] Redeploying {pid} ({status})...")
            try:
                # Force redeploy
                ahs._redeploy_product(pid)
                logger.info(f"Redeployed {pid}")
                
                # Update status to PUBLISHED if it was WAITING or PROMOTED, to reflect it's now live
                # (unless it was SOLD, then keep it SOLD)
                if status != "SOLD":
                    ledger.update_product_status(pid, "PUBLISHED", metadata=meta)
                
                time.sleep(2) # Avoid rate limits
                count += 1
            except Exception as e:
                logger.error(f"Failed to redeploy {pid}: {e}")
                
    logger.info(f"Total redeployed: {count}")

if __name__ == "__main__":
    fix_all_deployments()
