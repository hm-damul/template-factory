
import sys
import os
import json
import base64
from pathlib import Path
from types import SimpleNamespace

# Setup paths
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

# Set env for local testing
os.environ["DOWNLOAD_TOKEN_SECRET"] = "test-secret"
os.environ["VERCEL"] = "0"  # Local mode

# Mock request object
class MockRequest:
    def __init__(self, method, query, headers=None):
        self.method = method
        self.query = query
        self.headers = headers or {}
        self.body = b""

try:
    # Import modules
    import api.download
    import payment_api
    from order_store import get_order_store, Order, new_order_id
    
    # 1. Setup dummy order and package
    product_id = "test-prod-123"
    order_id = new_order_id()
    
    pkg_dir = project_root / "outputs" / product_id
    pkg_dir.mkdir(parents=True, exist_ok=True)
    pkg_path = pkg_dir / "package.zip"
    if not pkg_path.exists():
        pkg_path.write_text("dummy-content")
        
    store = get_order_store(project_root)
    order = Order(
        order_id=order_id,
        product_id=product_id,
        amount=10.0,
        currency="USD",
        status="paid",
        created_at="2023-01-01T00:00:00Z",
        provider="simulated",
        meta={}
    )
    store.upsert(order)
    print(f"Created order: {order_id}")
    
    # 2. Issue token
    token = payment_api.issue_download_token(
        project_root, 
        order_id=order_id, 
        product_id=product_id,
        ttl_seconds=3600
    )
    print(f"Issued token: {token}")
    
    # 3. Call api/download.py handler
    req = MockRequest(
        method="GET",
        query={"order_id": order_id, "token": token},
        headers={"Content-Type": "application/json"}
    )
    
    print("\nInvoking handler...")
    resp = api.download.handler(req)
    
    print("\nResponse:")
    print(f"Status: {resp.get('statusCode')}")
    headers = resp.get("headers", {})
    print(f"Headers: {json.dumps(headers, indent=2)}")
    
    body = resp.get("body")
    if resp.get("isBase64Encoded"):
        try:
            decoded = base64.b64decode(body)
            print(f"Body (decoded): {decoded.decode('utf-8')[:50]}...")
        except Exception as e:
            print(f"Body decode error: {e}")
    else:
        print(f"Body: {body[:100]}...")

except Exception as e:
    import traceback
    traceback.print_exc()
