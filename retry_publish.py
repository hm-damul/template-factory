
import sys
import os
from pathlib import Path
import time

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from src.ledger_manager import LedgerManager
from src.publisher import Publisher
from src.config import Config
from src.utils import get_logger

logger = get_logger("RetryPublish")

def retry_publish(product_id):
    print(f"Retrying publish for {product_id}...")
    lm = LedgerManager(Config.DATABASE_URL)
    publisher = Publisher(lm)
    
    product = lm.get_product(product_id)
    if not product:
        print(f"Product {product_id} not found!")
        return
        
    output_dir = os.path.join(os.getcwd(), "outputs", product_id)
    
    try:
        # This will trigger git push (again) and then verify
        result = publisher.publish_product(product_id, output_dir)
        print("Publish result:", result)
        
        if result["status"] == "PUBLISHED":
            print("Successfully published!")
            # Update status in DB if not already done by publisher (publisher usually returns dict, caller updates)
            # Wait, publisher.publish_product does NOT update DB status?
            # Let's check ProductFactory.resume_processing_product
            # It calls publisher.publish_product, then updates DB.
            
            deployment_url = result.get("url")
            lm.update_product_status(product_id, "PUBLISHED", metadata={
                "published_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "deployment_url": deployment_url
            })
            print(f"Updated status to PUBLISHED. URL: {deployment_url}")
            
    except Exception as e:
        print(f"Publish failed: {e}")

if __name__ == "__main__":
    retry_publish("20260219-063824-top-20-b2b-ecommerce-examples")
