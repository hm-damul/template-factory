
import sys
import os
from pathlib import Path
import json

# Add project root to sys.path
_root = str(Path(__file__).resolve().parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from api.pay.main import handler

class MockRequest:
    def __init__(self, method, path, body=None, query=None):
        self.method = method
        self.path = path
        self.url = path
        self.body = body if body else b""
        self.query = query if query else {}

def test_start():
    print("Testing /api/pay/start...")
    req = MockRequest(
        method="POST",
        path="/api/pay/start",
        body=json.dumps({"product_id": "test_product"}).encode("utf-8")
    )
    resp = handler(req)
    print(f"Response: {resp}")
    return resp

def test_check(order_id):
    print(f"Testing /api/pay/check for {order_id}...")
    req = MockRequest(
        method="GET",
        path=f"/api/pay/check?order_id={order_id}&product_id=test_product",
        query={"order_id": order_id, "product_id": "test_product"}
    )
    resp = handler(req)
    print(f"Response: {resp}")
    return resp

if __name__ == "__main__":
    # Ensure mode is mock for local test
    os.environ["PAYMENT_MODE"] = "mock"
    
    start_resp = test_start()
    if start_resp["statusCode"] == 200:
        body = json.loads(start_resp["body"])
        order_id = body.get("order_id")
        test_check(order_id)
    else:
        print("Start failed")
