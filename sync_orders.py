
import sys
import json
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT))

from order_store import FileOrderStore, Order

def sync():
    backend_path = PROJECT_ROOT / "backend" / "orders.json"
    data_dir = PROJECT_ROOT / "data"
    
    # Read backend orders
    backend_orders = []
    if backend_path.exists():
        try:
            data = json.loads(backend_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "orders" in data:
                backend_orders = data["orders"]
            elif isinstance(data, list):
                backend_orders = data
        except Exception as e:
            print(f"Error reading backend orders: {e}")

    print(f"Found {len(backend_orders)} orders in backend/orders.json")

    # Read data orders via Store
    store = FileOrderStore(data_dir)
    data_orders = store.list_orders()
    print(f"Found {len(data_orders)} orders in data/orders.json")

    # Merge (backend -> data)
    synced_count = 0
    for bo in backend_orders:
        order_id = bo.get("order_id")
        if not order_id:
            continue
        
        # Check if exists
        existing = store.get(order_id)
        if not existing:
            try:
                # Map dict to Order fields
                o = Order(
                    order_id=str(bo.get("order_id")),
                    product_id=str(bo.get("product_id")),
                    amount=float(bo.get("amount", 0)),
                    currency=str(bo.get("currency", "usd")),
                    status=str(bo.get("status", "pending")),
                    created_at=str(bo.get("created_at", "")),
                    provider=str(bo.get("provider", "simulated")),
                    provider_payment_id=str(bo.get("provider_payment_id", "")),
                    provider_invoice_url=str(bo.get("provider_invoice_url", "")),
                    meta=bo.get("meta") or {}
                )
                store.upsert(o)
                synced_count += 1
            except Exception as e:
                print(f"Failed to sync order {order_id}: {e}")
        else:
            # If exists but backend is 'paid' and data is 'pending', update it?
            # Or if backend has more info?
            # For now, let's assume backend is the source of truth for payment server orders.
            # If statuses differ, maybe update?
            if bo.get("status") == "paid" and existing.get("status") != "paid":
                 store.update_status(order_id, "paid")
                 synced_count += 1
                 print(f"Updated status for {order_id} to paid")

    print(f"Synced {synced_count} orders from backend to data.")

    # Now verify
    final_orders = store.list_orders()
    print(f"Total orders in data/orders.json: {len(final_orders)}")

if __name__ == "__main__":
    sync()
