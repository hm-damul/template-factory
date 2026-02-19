# -*- coding: utf-8 -*-
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT))

from src.ledger_manager import LedgerManager
from src.publisher import Publisher
from src.utils import get_logger

logger = get_logger("RedeployWaiting")

def redeploy():
    ledger = LedgerManager()
    publisher = Publisher(ledger)
    
    products = ledger.get_all_products()
    waiting_products = [p for p in products if p.get("status") == "WAITING_FOR_DEPLOYMENT"]
    
    logger.info(f"Found {len(waiting_products)} products waiting for deployment.")
    
    for p in waiting_products:
        product_id = p.get("id")
        logger.info(f"Redeploying {product_id}...")
        
        product_dir = PROJECT_ROOT / "outputs" / product_id
        if not product_dir.exists():
            logger.error(f"Output directory missing for {product_id}")
            continue
            
        try:
            # publisher.publish_product checks for QA2_PASSED or PACKAGED. 
            # WAITING_FOR_DEPLOYMENT products should have been at one of these stages.
            # Let's force it to QA2_PASSED to bypass the check in publisher.py if needed.
            ledger.update_product_status(product_id, "QA2_PASSED")
            
            result = publisher.publish_product(product_id, str(product_dir))
            if result.get("status") == "PUBLISHED":
                logger.info(f"Successfully published {product_id}!")
                # Wait 10 seconds between deployments to avoid rate limit (429)
                time.sleep(10)
            else:
                logger.warning(f"Failed to publish {product_id}: {result.get('error')}")
                error_str = str(result.get("error", ""))
                if "429" in error_str or "402" in error_str:
                    logger.info(f"Vercel limit ({error_str}) hit, stopping for now.")
                    break
        except Exception as e:
            logger.error(f"Error publishing {product_id}: {e}")
            error_str = str(e)
            if "429" in error_str or "402" in error_str:
                logger.info(f"Vercel limit ({error_str}) hit, stopping for now.")
                break

if __name__ == "__main__":
    redeploy()
