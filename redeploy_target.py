
import sys
import os
from pathlib import Path
import logging

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent))

from src.ledger_manager import LedgerManager
from src.publisher import Publisher
from src.config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RedeployTarget")

def redeploy():
    product_id = "20260220-211248-digital-asset-bundle-2026-02-2"
    logger.info(f"Starting manual redeployment for {product_id}...")
    
    ledger = LedgerManager(Config.DATABASE_URL)
    publisher = Publisher(ledger)
    
    # Check if product exists
    product = ledger.get_product(product_id)
    if not product:
        logger.error(f"Product {product_id} not found!")
        return

    output_dir = os.path.join(Config.OUTPUT_DIR, product_id)
    
    try:
        # Force publish using Git Push
        logger.info("Calling publish_product...")
        result = publisher.publish_product(product_id, output_dir)
        
        logger.info("Redeployment result:")
        logger.info(result)
        
        if result.get("status") == "PUBLISHED":
            logger.info(f"Successfully redeployed. URL: {result.get('url')}")
        else:
            logger.error("Redeployment failed.")
            
    except Exception as e:
        logger.error(f"An error occurred during redeployment: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    redeploy()
