import os
import sys
from pathlib import Path

# Add current dir to sys.path
sys.path.insert(0, os.getcwd())

from src.ledger_manager import LedgerManager
from src.publisher import Publisher
from src.config import Config

def redeploy(product_id):
    ledger = LedgerManager()
    publisher = Publisher(ledger)
    
    # Get product info
    product = ledger.get_product(product_id)
    if not product:
        print(f"Error: Product {product_id} not found in ledger")
        return
    
    # Path to build output
    build_dir = Path("outputs") / product_id
    if not build_dir.exists():
        print(f"Error: Build directory {build_dir} not found")
        return
        
    print(f"Redeploying {product_id}...")
    
    # Generate project name (same as original)
    project_name = publisher._sanitize_project_name(f"meta-passive-income-{product_id}")
    
    # Re-deploy
    try:
        url = publisher._deploy_to_vercel(product_id, project_name, str(build_dir))
        print(f"Success! New URL: {url}")
        
        # Update ledger
        metadata = product.get('metadata', {})
        metadata['deployment_url'] = url
        ledger.update_product(product_id, status="PUBLISHED", metadata=metadata)
        print("Ledger updated.")
    except Exception as e:
        print(f"Redeploy failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python redeploy_product.py <product_id>")
    else:
        redeploy(sys.argv[1])
