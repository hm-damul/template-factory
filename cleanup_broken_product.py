import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from src.ledger_manager import LedgerManager
lm = LedgerManager()
try:
    lm.delete_product("test_optimized_v3")
    print("Deleted test_optimized_v3 from ledger")
except Exception as e:
    print(f"Error deleting product: {e}")
