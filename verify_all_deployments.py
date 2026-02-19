from src.ledger_manager import LedgerManager
from src.config import Config
import requests
import json

def verify_all():
    ledger = LedgerManager(Config.DATABASE_URL)
    products = ledger.list_products()
    
    print(f"Total products: {len(products)}")
    
    for p in products:
        # Check all products that might have a URL
        pid = p.get("id")
        status = p.get("status")
        meta = p.get("metadata") or {}
        if isinstance(meta, str):
            meta = json.loads(meta)
        
        url = meta.get("deployment_url")
        if not url:
            # Only complain if it's supposed to be deployed
            if status in ["PUBLISHED", "PROMOTED", "SOLD"]:
                print(f"[FAIL] {pid} ({status}): No deployment URL")
            continue
            
        try:
            print(f"Checking {pid} ({status}) -> {url}")
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                text_lower = r.text.lower()
                if "<title>index of /</title>" in text_lower or "<h1>index of /</h1>" in text_lower or "index of /" in text_lower:
                    print(f"[FAIL] {pid}: Directory Listing (200 OK)")
                elif "authentication required" in text_lower: # Vercel 401
                    print(f"[FAIL] {pid}: Vercel 401 Unauthorized")
                else:
                    print(f"[PASS] {pid}: OK")
            else:
                print(f"[FAIL] {pid}: Status {r.status_code}")
        except Exception as e:
            print(f"[FAIL] {pid}: Exception {e}")

if __name__ == "__main__":
    verify_all()
