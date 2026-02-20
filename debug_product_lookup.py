
from src.ledger_manager import LedgerManager
import json

def check_product(pid):
    lm = LedgerManager()
    p = lm.get_product(pid)
    if p:
        print(f"Product found: {pid}")
        print(f"Status: {p['status']}")
        print(f"Title: {p['title']}")
        print(f"Meta: {json.dumps(p.get('metadata'), indent=2, ensure_ascii=False)}")
    else:
        print(f"Product NOT found: {pid}")
        # Try fuzzy search
        print("Searching for similar...")
        all_p = lm.list_products()
        for prod in all_p:
            if "digital-asset-bundle" in prod['id'] or "20260220" in prod['id']:
                print(f"Found similar: {prod['id']} - {prod['title']}")

if __name__ == "__main__":
    target_id = "20260220-211248-digital-asset-bundle-2026-02-2"
    check_product(target_id)
