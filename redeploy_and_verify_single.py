
import logging
from src.auto_heal_system import AutoHealSystem
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    product_id = "20260215-212725-token-gated-content-revenue-au"
    if len(sys.argv) > 1:
        product_id = sys.argv[1]
        
    logger.info(f"Redeploying and verifying product: {product_id}")
    
    healer = AutoHealSystem()
    healer._redeploy_product(product_id)
    
    logger.info("Done.")

if __name__ == "__main__":
    main()
