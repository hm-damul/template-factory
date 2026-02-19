import sys
import json
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from src.ledger_manager import LedgerManager
lm = LedgerManager()
products = lm.list_products(limit=5)

for p in products:
    print(f"Product ID: {p['id']}")
    print(f"Status: {p['status']}")
    meta = p.get("metadata", {})
    # meta can be a string in some versions, check type
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except:
            pass
            
    print(f"Deployment URL: {meta.get('deployment_url')}")
    print(f"Promotion Channels: {meta.get('promoted_channels')}")
    print("-" * 30)
