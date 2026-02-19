
import requests
import json
from src.ledger_manager import LedgerManager
from src.config import Config

def main():
    ledger = LedgerManager(Config.DATABASE_URL)
    pid = "20260215-212725-token-gated-content-revenue-au"
    prod = ledger.get_product(pid)
    
    if not prod:
        print(f"Product {pid} not found")
        return

    meta = prod.get("metadata", {})
    if isinstance(meta, str):
        meta = json.loads(meta)
        
    url = meta.get("deployment_url")
    print(f"URL: {url}")
    
    if url:
        try:
            r = requests.get(url, timeout=10)
            print(f"Status: {r.status_code}")
            if "index of" in r.text.lower():
                print("Result: Directory Listing Detected")
            else:
                print("Result: OK (No Directory Listing)")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
