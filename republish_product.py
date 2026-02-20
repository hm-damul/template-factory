import sys
import os
import logging
from src.ledger_manager import LedgerManager
from src.publisher import Publisher
from src.config import Config

# Configure logging to show info
logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python republish_product.py <product_id>")
        sys.exit(1)

    product_id = sys.argv[1]
    lm = LedgerManager()
    publisher = Publisher(lm)
    
    output_dir = os.path.join(Config.OUTPUT_DIR, product_id)
    
    print(f"Republishing {product_id}...")
    try:
        # Check if output dir exists
        if not os.path.exists(output_dir):
            print(f"Output directory not found: {output_dir}")
            sys.exit(1)
            
        result = publisher.publish_product(product_id, output_dir)
        print("Result:", result)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
