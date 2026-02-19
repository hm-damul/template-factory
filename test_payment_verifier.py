
import logging
from src.ledger_manager import LedgerManager
from src.config import Config
from src.payment_flow_verifier import PaymentFlowVerifier
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    lm = LedgerManager(Config.DATABASE_URL)
    products = lm.list_products()
    published = [p for p in products if p.get("status") in ["PUBLISHED", "SOLD", "PROMOTED"]]
    
    if not published:
        print("No published products found.")
        return

    print(f"Found {len(published)} published products.")
    
    verifier = PaymentFlowVerifier()
    
    # Test the first one that has a deployment URL
    for p in published:
        meta = p.get("metadata", {})
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except:
                continue
                
        url = meta.get("deployment_url")
        if url:
            pid = p.get('product_id') or p.get('id')
            print(f"Testing product: {pid} at {url}")
            is_verified, msg, details = verifier.verify_payment_flow(pid, url, 1.0)
            print(f"Result: {is_verified}")
            print(f"Message: {msg}")
            print(f"Details: {details}")
            break
    else:
        print("No products with deployment_url found.")

if __name__ == "__main__":
    main()
