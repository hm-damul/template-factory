# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT))

from src.ledger_manager import LedgerManager
from src.publisher import Publisher
from src.utils import get_logger

logger = get_logger("RedeployLatest")

def redeploy():
    ledger = LedgerManager()
    # Get the latest product from outputs directory
    outputs_dir = PROJECT_ROOT / "outputs"
    product_dirs = [d for d in outputs_dir.iterdir() if d.is_dir()]
    if not product_dirs:
        logger.error("No products found in outputs directory.")
        return

    # Sort by modification time to get the latest
    latest_dir = max(product_dirs, key=lambda d: d.stat().st_mtime)
    product_id = latest_dir.name
    logger.info(f"Latest product detected: {product_id}")

    # Initialize Publisher
    publisher = Publisher(ledger)
    
    # Update status to allow redeploy if already published
    product = ledger.get_product(product_id)
    if product and product.get("status") == "PUBLISHED":
        logger.info(f"Product {product_id} is already PUBLISHED. Resetting status to QA2_PASSED to allow redeploy.")
        ledger.update_product_status(product_id, "QA2_PASSED")

    # Trigger redeploy
    try:
        logger.info(f"Redeploying {product_id} to Vercel...")
        result = publisher.publish_product(product_id, str(latest_dir))
        logger.info(f"Redeploy successful! URL: {result.get('metadata', {}).get('deployment_url')}")
    except Exception as e:
        logger.error(f"Redeploy failed: {e}")

if __name__ == "__main__":
    redeploy()
