# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to sys.path
root = Path(__file__).resolve().parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

load_dotenv()

def test_upstash():
    from order_store import get_order_store, Order
    import uuid
    import time

    url = os.getenv("UPSTASH_REDIS_REST_URL")
    token = os.getenv("UPSTASH_REDIS_REST_TOKEN")

    if not url or not token:
        print("SKIP: Upstash credentials not found in .env")
        return

    print(f"Testing Upstash at: {url}")
    store = get_order_store(root)
    
    order_id = f"test_{int(time.time())}"
    order = Order(
        order_id=order_id,
        product_id="test_prod",
        amount=1.0,
        currency="USD",
        status="pending",
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        provider="simulated"
    )

    try:
        # Test UPSERT
        print(f"Upserting order: {order_id}")
        store.upsert(order)
        
        # Test GET
        print(f"Getting order: {order_id}")
        retrieved = store.get(order_id)
        if retrieved and retrieved["order_id"] == order_id:
            print("SUCCESS: Get order match")
        else:
            print(f"FAILED: Get order mismatch. Got: {retrieved}")

        # Test UPDATE STATUS
        print(f"Updating status to paid: {order_id}")
        store.update_status(order_id, "paid")
        updated = store.get(order_id)
        if updated and updated["status"] == "paid":
            print("SUCCESS: Status update match")
        else:
            print(f"FAILED: Status update mismatch. Got: {updated}")

    except Exception as e:
        print(f"ERROR: {str(e)}")

if __name__ == "__main__":
    test_upstash()
