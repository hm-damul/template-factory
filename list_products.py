
import sys
from pathlib import Path
import json

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT))

from src.ledger_manager import LedgerManager

def list_all_products():
    lm = LedgerManager()
    products = lm.list_products()
    
    print(f"{'ID':<40} | {'Status':<15} | {'Topic'}")
    print("-" * 80)
    for p in products:
        print(f"{p['id']:<40} | {p['status']:<15} | {p['topic']}")

if __name__ == "__main__":
    list_all_products()
