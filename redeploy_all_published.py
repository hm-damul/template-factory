
import logging
import os
import sys
import json
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from src.auto_heal_system import AutoHealSystem
from src.ledger_manager import LedgerManager
from src.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("RedeployAll")

def main():
    logger.info("Starting bulk redeployment of all PUBLISHED products...")
    
    # Initialize AutoHealSystem
    auto_heal = AutoHealSystem()
    ledger = LedgerManager(Config.DATABASE_URL)
    
    # Get all products
    products = ledger.get_all_products()
    
    # Filter for PUBLISHED, PROMOTED, or SOLD products
    target_products = [
        p for p in products 
        if p.get("status") in ["PUBLISHED", "PROMOTED", "SOLD"]
    ]
    
    logger.info(f"Found {len(target_products)} products to redeploy.")
    
    from src.progress_tracker import update_progress
    total = len(target_products)
    for i, prod in enumerate(target_products):
        product_id = prod["id"]
        status = prod["status"]
        msg = f"[{i+1}/{total}] Redeploying {product_id} (Status: {status})..."
        logger.info(msg)
        update_progress("Bulk Redeploy", f"Processing {i+1}/{total}", int((i/total)*100), msg, product_id)
        
        try:
            # Force redeployment
            auto_heal._redeploy_product(product_id)
            logger.info(f"Successfully redeployed {product_id}")
        except Exception as e:
            logger.error(f"Failed to redeploy {product_id}: {e}")
    update_progress("Bulk Redeploy", "Completed", 100, f"Processed {total} products", "")

    logger.info("Bulk redeployment completed.")

if __name__ == "__main__":
    main()
