
import os
import sys
import time
from pathlib import Path
import json

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT))

from src.ledger_manager import LedgerManager
from src.publisher import Publisher
from src.local_verifier import LocalVerifier
from src.utils import get_logger

logger = get_logger("DeployAll")

def deploy_all_products():
    lm = LedgerManager()
    lv = LocalVerifier()
    pub = Publisher(lm)
    
    outputs_dir = PROJECT_ROOT / "outputs"
    if not outputs_dir.exists():
        logger.error("Outputs directory not found.")
        return

    # 1. Get all products from outputs directory
    output_products = [d for d in outputs_dir.iterdir() if d.is_dir()]
    output_products.sort(key=lambda x: x.stat().st_mtime) # Oldest first? Or newest? Let's do oldest first to clear backlog.

    logger.info(f"Found {len(output_products)} products in outputs directory.")

    # 2. Get current ledger status
    ledger_products = lm.list_products()
    ledger_map = {p['id']: p for p in ledger_products}

    success_count = 0
    fail_count = 0
    skip_count = 0

    for product_dir in output_products:
        pid = product_dir.name
        logger.info(f"--- Processing {pid} ---")

        # Check if already published
        if pid in ledger_map:
            status = ledger_map[pid]['status']
            if status == 'PUBLISHED':
                logger.info(f"  Skipping: Already PUBLISHED.")
                skip_count += 1
                continue
            elif status == 'PROMOTED': # Assuming PROMOTED means effectively published/promoted
                logger.info(f"  Skipping: Already PROMOTED.")
                skip_count += 1
                continue
        else:
            # Register if missing
            logger.info(f"  Registering missing product {pid} to ledger...")
            try:
                # Try to load title from schema
                schema_path = product_dir / "product_schema.json"
                topic = "Unknown Topic"
                if schema_path.exists():
                    try:
                        schema = json.loads(schema_path.read_text(encoding="utf-8"))
                        topic = schema.get("title", topic)
                    except:
                        pass
                
                lm.create_product(topic=topic, product_id=pid)
                lm.update_product_status(pid, "PACKAGED")
            except Exception as e:
                logger.error(f"  Failed to register {pid}: {e}")
                fail_count += 1
                continue

        # 3. Verify Local (Repair if needed)
        logger.info("  Verifying/Repairing locally...")
        try:
            lv.verify_and_repair_product(str(product_dir))
        except Exception as e:
            logger.error(f"  Verification failed: {e}")
            # We might continue anyway if it's just a warning, but let's be safe
            # Actually local_verifier usually fixes things.
        
        # 4. Deploy
        logger.info("  Deploying to Vercel...")
        try:
            result = pub.publish_product(pid, str(product_dir))
            if result['status'] == 'PUBLISHED':
                url = result.get('metadata', {}).get('deployment_url')
                logger.info(f"  SUCCESS: Deployed to {url}")
                success_count += 1
                
                # Update ledger if not already done by publisher (Publisher usually updates it)
                # But let's double check
                p = lm.get_product(pid)
                if p and p.status != 'PUBLISHED':
                     lm.update_product_status(pid, "PUBLISHED")
            else:
                logger.error(f"  Failed to deploy: {result['status']}")
                fail_count += 1
        except Exception as e:
            logger.error(f"  Deployment Exception: {e}")
            fail_count += 1
            
        # Sleep a bit to avoid hitting rate limits too hard (Publisher handles some, but extra safety)
        time.sleep(2)

    logger.info("=" * 50)
    logger.info(f"Deployment Complete.")
    logger.info(f"Success: {success_count}")
    logger.info(f"Failed: {fail_count}")
    logger.info(f"Skipped: {skip_count}")

if __name__ == "__main__":
    deploy_all_products()
