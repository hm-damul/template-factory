# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT))

from src.ledger_manager import LedgerManager
from auto_pilot import ProductFactory
from src.config import Config
from src.utils import get_logger, ProductionError
from src.qa_manager import QAManager
from src.package_manager import PackageManager

logger = get_logger("RecoveryManager")

def recover():
    ledger = LedgerManager(Config.DATABASE_URL)
    factory = ProductFactory()
    
    products = ledger.get_all_products()
    # We want to recover anything that isn't PUBLISHED or WAITING_FOR_DEPLOYMENT
    failed_products = [p for p in products if p.get("status") in ["PIPELINE_FAILED", "QA2_FAILED", "QA1_FAILED"]]
    
    logger.info(f"Found {len(failed_products)} failed products to recover.")
    
    for p in failed_products:
        product_id = p.get("id")
        topic = p.get("topic")
        status = p.get("status")
        
        logger.info(f"Attempting recovery for {product_id} (Status: {status}, Topic: {topic})")
        
        out_dir = PROJECT_ROOT / "outputs" / product_id
        
        try:
            if not out_dir.exists():
                logger.info(f"Output directory missing for {product_id}. Regenerating...")
                factory.run_batch(batch_size=1, languages=["en", "ko"], topic=topic)
                continue

            # If output exists, try to resume
            logger.info(f"Resuming pipeline for {product_id} from {status}...")
            factory.resume_processing_product(product_id, topic, str(out_dir))
                
        except Exception as e:
            logger.error(f"Failed to recover {product_id}: {e}")

    logger.info("Recovery process completed.")

if __name__ == "__main__":
    recover()
