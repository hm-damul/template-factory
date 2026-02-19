
import os
import sys
import json
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from promotion_dispatcher import dispatch_publish
from src.ledger_manager import LedgerManager

def test_x_posting():
    product_id = "20260214-130903-ai-trading-bot"
    print(f"Testing X posting for: {product_id}")
    
    # Load secrets into environment variables for the dispatcher
    secrets_path = PROJECT_ROOT / "data" / "secrets.json"
    if secrets_path.exists():
        secrets = json.loads(secrets_path.read_text(encoding="utf-8"))
        for k, v in secrets.items():
            if v:
                os.environ[k] = str(v)
    
    # Enable real social posting
    os.environ["SOCIAL_MOCK"] = "0"
    
    # Run dispatch
    res = dispatch_publish(product_id)
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    test_x_posting()
