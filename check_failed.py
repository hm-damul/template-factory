
from src.ledger_manager import LedgerManager
from src.config import Config
import json

def check():
    lm = LedgerManager(Config.DATABASE_URL)
    products = lm.list_products()
    for p in products:
        if "FAILED" in p["status"]:
            print(f"ID: {p['id']}")
            print(f"Status: {p['status']}")
            print(f"Topic: {p['topic']}")
            metadata = p.get("metadata_json")
            if metadata:
                try:
                    meta_obj = json.loads(metadata)
                    print(f"Error: {meta_obj.get('error')}")
                    print(f"Stage: {meta_obj.get('stage')}")
                except:
                    print(f"Metadata: {metadata}")
            print("-" * 20)

if __name__ == "__main__":
    check()
