
from src.ledger_manager import LedgerManager
from collections import Counter
import os
import shutil

def main():
    lm = LedgerManager()
    products = lm.list_products()
    print(f"Total products: {len(products)}")
    
    status_counts = Counter(p['status'] for p in products)
    print("Status counts:", status_counts)
    
    # List directories in outputs
    output_dirs = []
    if os.path.exists("outputs"):
        output_dirs = [d for d in os.listdir("outputs") if os.path.isdir(os.path.join("outputs", d))]
    print(f"Total output directories: {len(output_dirs)}")
    
    # Check intersection
    product_ids = set(p['id'] for p in products)
    orphan_dirs = [d for d in output_dirs if d not in product_ids]
    print(f"Orphan output directories: {len(orphan_dirs)}")
    
    # Check published/promoted count
    kept_products = [p for p in products if p['status'] in ['PUBLISHED', 'PROMOTED']]
    print(f"Published/Promoted products: {len(kept_products)}")
    
    # Check if we can delete failed ones
    failed_products = [p for p in products if p['status'] in ['FAILED', 'ERROR']]
    print(f"Failed products: {len(failed_products)}")
    
    # Check if we can delete draft ones if they are old
    draft_products = [p for p in products if p['status'] == 'DRAFT']
    print(f"Draft products: {len(draft_products)}")

if __name__ == "__main__":
    main()
