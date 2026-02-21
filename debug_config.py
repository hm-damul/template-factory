
import sys
from pathlib import Path
import json

# Add src to path
root = Path(__file__).resolve().parent
sys.path.append(str(root / "src"))

try:
    from src.promotion_dispatcher import load_channel_config
    cfg = load_channel_config()
    print("Config loaded successfully")
    print(json.dumps(cfg.get("blog", {}), indent=2))
except Exception as e:
    print(f"Error loading config: {e}")

from src.audit_bot import SystemAuditBot
bot = SystemAuditBot()
# Check internal logic of audit_promotions regarding config loading
import src.audit_bot
print(f"Audit Bot File: {src.audit_bot.__file__}")
