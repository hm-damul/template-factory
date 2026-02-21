
import sys
from pathlib import Path
sys.path.append(str(Path(".").resolve()))
from src.ledger_manager import LedgerManager
from src.config import Config

lm = LedgerManager(Config.DATABASE_URL)
pid = "20260220-211248-digital-asset-bundle-2026-02-2"
prod = lm.get_product(pid)
if prod:
    print(f"Product: {prod['topic']}")
    print(f"Status: {prod['status']}")
    print(f"Metadata: {prod['metadata']}")
else:
    print("Product not found")
