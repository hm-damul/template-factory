
import sys
from collections import Counter
from pathlib import Path
sys.path.append(str(Path.cwd()))
from src.ledger_manager import LedgerManager
from src.config import Config

lm = LedgerManager(Config.DATABASE_URL)
products = lm.list_products(limit=1000)
stats = Counter([p['status'] for p in products])

print("=== Product Status Distribution ===")
for k, v in stats.items():
    print(f"{k}: {v}")

print("\n=== Audit Bot Check ===")
try:
    from src.audit_bot import SystemAuditBot
    bot = SystemAuditBot()
    report = bot.run_full_audit()
    print(f"Healthy Products: {report['summary']['healthy_products']}/{report['summary']['total_products']}")
    print(f"Healthy Promotions: {report['summary']['healthy_promotions']}/{report['summary']['total_promotions']}")
    if report['summary']['broken_products'] > 0:
        print("\nBroken Products Details:")
        for item in report['details']:
            if item.get('type') == 'product' and item.get('issues'):
                print(f"- {item['product_id']}: {item['issues']}")

    if report['summary']['broken_promotions'] > 0:
        print("\nBroken Promotions Details:")
        for item in report['details']:
            if item.get('type').startswith('promotion_') and item.get('issues'):
                print(f"- {item['product_id']} ({item['type']}): {item['issues']}")
except Exception as e:
    print(f"Audit Bot Error: {e}")
