import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from src.ledger_manager import LedgerManager
lm = LedgerManager()
products = lm.list_products()

print(f"Total products: {len(products)}")
status_counts = {}
for p in products:
    s = p.get("status", "UNKNOWN")
    status_counts[s] = status_counts.get(s, 0) + 1

print("Status counts:", status_counts)

# Show a few examples of non-published products
print("\nSample non-published products:")
count = 0
for p in products:
    if p.get("status") != "PUBLISHED":
        print(f"- {p['id']} ({p['status']})")
        count += 1
        if count >= 5: break
