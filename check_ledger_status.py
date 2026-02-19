import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.append(str(PROJECT_ROOT))

from src.ledger_manager import LedgerManager
from src.config import Config

lm = LedgerManager(Config.DATABASE_URL)
products = lm.list_products()

print(f"Total products: {len(products)}")
status_counts = {}
for p in products:
    s = p.get("status", "UNKNOWN")
    status_counts[s] = status_counts.get(s, 0) + 1
    
print("\nStatus counts:")
for s, c in status_counts.items():
    print(f"  {s}: {c}")

print("\nSample Products:")
for p in products[:5]:
    print(f"  {p['id']} ({p.get('status')})")
