
import sys
import os
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT))

from src.ledger_manager import LedgerManager
from src.publisher import Publisher
from promotion_factory import mark_ready_to_publish
from promotion_dispatcher import dispatch_publish

def test_bulk_publish_logic():
    lm = LedgerManager()
    products = lm.list_products(limit=3)
    
    if len(products) < 2:
        print("Need at least 2 products to test bulk publish.")
        return

    ids_to_publish = [p['id'] for p in products[:2]]
    print(f"Testing bulk publish for: {ids_to_publish}")

    outputs_dir = PROJECT_ROOT / "outputs"
    
    for pid in ids_to_publish:
        print(f"\n--- Processing {pid} ---")
        try:
            d = outputs_dir / pid
            if not d.exists():
                print(f"Directory {d} not found, creating dummy.")
                d.mkdir(parents=True, exist_ok=True)
                (d / "index.html").write_text(f"<html><body>Test {pid}</body></html>")

            # 0. Ensure status is PACKAGED
            print(f"Updating {pid} status to PACKAGED...")
            lm.update_product_status(pid, status="PACKAGED")

            # 1. Mark ready
            print(f"Marking {pid} as ready to publish...")
            mark_ready_to_publish(product_dir=d, product_id=pid)

            # 2. Dispatch promotions
            print(f"Dispatching promotions for {pid}...")
            try:
                dispatch_publish(pid)
            except Exception as e:
                print(f"Promotion dispatch failed (expected if webhooks not set): {e}")

            # 3. Vercel deployment
            print(f"Starting Vercel deployment for {pid}...")
            pub = Publisher(lm)
            res = pub.publish_product(pid, str(d))
            print(f"Result for {pid}: {res['status']} - {res.get('metadata', {}).get('deployment_url', 'No URL')}")

        except Exception as e:
            print(f"Failed to process {pid}: {e}")

if __name__ == "__main__":
    test_bulk_publish_logic()
