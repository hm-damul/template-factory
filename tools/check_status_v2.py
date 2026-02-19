import sys
import os
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

print(f"Project root: {project_root}")

try:
    from src.ledger_manager import LedgerManager
    lm = LedgerManager()
    products = lm.list_products()

    print(f"Total products in ledger: {len(products)}")
    
    counts = {}
    for p in products:
        s = p.get("status", "UNKNOWN")
        counts[s] = counts.get(s, 0) + 1
    
    print("Status distribution:")
    for s, c in counts.items():
        print(f"  {s}: {c}")

    # Check for any PUBLISHED products
    published = [p for p in products if p.get("status") == "PUBLISHED"]
    print(f"\nPublished products: {len(published)}")
    
    # Check for QA_PASSED products (ready to publish)
    qa_passed = [p for p in products if p.get("status") == "QA_PASSED"]
    print(f"QA_PASSED products (Ready to Publish): {len(qa_passed)}")

except Exception as e:
    print(f"Error: {e}")
