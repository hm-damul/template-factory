
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from src.ledger_manager import LedgerManager
import json

lm = LedgerManager("sqlite:///data/ledger.db")
p = lm.get_product("20260215-014951-automated-crypto-tax-reporting")
if p:
    print(json.dumps(p.get("metadata", {}), indent=2))
else:
    print("Product not found")
