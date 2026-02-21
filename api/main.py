from http.server import BaseHTTPRequestHandler
import json
import os
import sys
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Cloud-specific imports
try:
    from . import nowpayments
except ImportError:
    # If running locally in api folder without package structure
    import nowpayments

class handler(BaseHTTPRequestHandler):
    def _send_json(self, status, data):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_GET(self):
        try:
            parsed_path = urlparse(self.path)
            path = parsed_path.path
            query = parse_qs(parsed_path.query)
            
            print(f"[DEBUG] Request path: {path}")

            if path.startswith("/api/"):
                if "/api/pay/check" in path:
                    self.handle_check(query)
                elif "/api/pay/debug" in path:
                    self.handle_debug()
                elif "/api/pay/start" in path:
                    # Convert query params (lists) to single values for handle_start
                    data = {k: v[0] for k, v in query.items() if v}
                    self.handle_start(data)
                elif "/health" in path:
                    self._send_json(200, {"status": "ok"})
                else:
                    self._send_json(404, {"error": "not_found", "path": path})
            elif path.startswith("/checkout/"):
                # Rewrite /checkout/XXX to /outputs/XXX/index.html
                # Remove /checkout/ prefix
                product_path = path[len("/checkout/"):]
                # Handle query params if any (already parsed in path, but let's be safe)
                if "?" in product_path:
                    product_path = product_path.split("?")[0]
                
                # Construct target path
                target_path = f"outputs/{product_path}/index.html"
                print(f"[DEBUG] Rewriting checkout path {path} to {target_path}")
                self.serve_static(target_path)
            else:
                # Serve static files locally
                self.serve_static(path)
        except Exception as e:
            self._send_json(500, {"error": str(e), "trace": "do_GET"})

    def serve_static(self, path):
        # Security: prevent directory traversal
        if ".." in path:
            self.send_error(403)
            return
            
        # Map / to index.html
        if path == "/":
            path = "/index.html"
            
        # Remove leading slash
        if path.startswith("/"):
            path = path[1:]
            
        # Determine root directory
        root_dir = Path(".").resolve()
        
        # Check if we are running inside api folder
        if root_dir.name == "api":
            root_dir = root_dir.parent
            
        file_path = root_dir / path
        
        print(f"[DEBUG] serve_static: path={path}, root_dir={root_dir}, file_path={file_path}, exists={file_path.exists()}")
        
        if file_path.exists() and file_path.is_file():
            self.send_response(200)
            # MIME types
            if path.endswith(".html"):
                self.send_header('Content-type', 'text/html')
            elif path.endswith(".css"):
                self.send_header('Content-type', 'text/css')
            elif path.endswith(".js"):
                self.send_header('Content-type', 'application/javascript')
            elif path.endswith(".json"):
                self.send_header('Content-type', 'application/json')
            elif path.endswith(".png"):
                self.send_header('Content-type', 'image/png')
            else:
                self.send_header('Content-type', 'application/octet-stream')
            self.end_headers()
            with open(file_path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404, f"File not found: {path}")

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8')) if body else {}
            
            parsed_path = urlparse(self.path)
            path = parsed_path.path

            if "/api/pay/start" in path:
                self.handle_start(data)
            elif "/api/pay/token" in path:
                self.handle_token(data)
            else:
                self._send_json(404, {"error": "not_found", "path": path})
        except Exception as e:
            self._send_json(500, {"error": str(e), "trace": "do_POST"})

    def handle_debug(self):
        self._send_json(200, {
            "status": "ok", 
            "env_keys": list(os.environ.keys()),
            "nowpayments_loaded": True
        })

    def handle_check(self, query):
        # We use payment_id as order_id in this stateless flow
        payment_id = query.get('order_id', [''])[0]
        product_id = query.get('product_id', [''])[0]
        
        if not payment_id:
             self._send_json(400, {"error": "order_id_missing"})
             return

        # Check status via NOWPayments
        payment_info = nowpayments.get_payment_status(payment_id)
        
        status = "pending"
        download_url = None
        provider_status = "unknown"
        
        if payment_info:
            provider_status = payment_info.get("payment_status", "unknown")
            # Map NOWPayments status to our status
            # finished, confirmed, sending -> paid
            # waiting, confirming -> pending
            if provider_status in ["finished", "confirmed", "sending"]:
                status = "paid"
                # Secure download link logic
                # Determine package filename from schema for security/obfuscation
                package_filename = "package.zip"
                try:
                    # Robust path finding for Vercel and Local
                    # Vercel: /var/task/outputs/... or similar, but we use relative paths
                    # api/main.py is usually in api/ folder. 
                    # We need to look for ../outputs (local) or outputs (if bundled differently)
                    
                    possible_paths = [
                        Path(f"outputs/{product_id}/product_schema.json"),      # Project root or bundled
                        Path(f"../outputs/{product_id}/product_schema.json"),   # From api/ folder
                        Path(os.getcwd()) / f"outputs/{product_id}/product_schema.json" # Absolute
                    ]
                    
                    found_schema = False
                    for schema_path in possible_paths:
                        if schema_path.exists():
                            s = json.loads(schema_path.read_text(encoding="utf-8"))
                            package_filename = s.get("package_file", "package.zip")
                            found_schema = True
                            break
                    
                    if not found_schema:
                         print(f"Warning: Schema not found for {product_id}, using default package.zip")

                except Exception as e:
                    print(f"Error reading schema for package file: {e}")

                download_url = f"/outputs/{product_id}/{package_filename}"
            elif provider_status in ["failed", "refunded", "expired"]:
                status = "failed"
            else:
                status = "pending" # waiting, confirming
        else:
            # Fallback if API fails or ID invalid
            status = "pending"

        self._send_json(200, {
            "status": status, 
            "order_id": payment_id,
            "download_url": download_url,
            "provider_status": provider_status
        })

    def handle_start(self, data):
        product_id = data.get('product_id', '')
        # Default price
        price = '19.90'
        
        # Try to load price from schema
        try:
            # Assume running from project root or api folder, try both
            # If running from root: outputs/{product_id}/product_schema.json
            # If running from api/: ../outputs/{product_id}/product_schema.json
            schema_path = Path(f"outputs/{product_id}/product_schema.json")
            if not schema_path.exists():
                schema_path = Path(f"../outputs/{product_id}/product_schema.json")
            
            if schema_path.exists():
                s = json.loads(schema_path.read_text(encoding="utf-8"))
                # 1. Try pricing section
                p_val = s.get("sections", {}).get("pricing", {}).get("price", "")
                if p_val:
                    price = str(float(p_val.replace('$', '').replace(',', '')))
                # 2. Fallback to market_analysis
                elif "market_analysis" in s:
                     p_val = s["market_analysis"].get("our_price")
                     if p_val:
                         price = str(float(p_val))
        except Exception as e:
            print(f"Error loading schema price: {e}")
            
        # Use provided price if it's not the default fallback (but trust schema more)
        # Actually, we should trust the schema price over the client input if possible, 
        # but for now let's use schema price if we found it, otherwise fallback to data.get or default.
        if price == '19.90':
             price = data.get('price_amount', '19.90')
        
        # Generate Order ID for internal tracking (if we had DB)
        # For stateless, we use random or timestamp
        internal_order_id = f"ord_{secrets.token_hex(8)}"
        
        # Call NOWPayments to create invoice (Hosted Page is better for autonomous sales)
        payment_data = nowpayments.create_invoice(
            order_id=internal_order_id,
            product_id=product_id,
            amount=price,
            currency="usd"
        )
        
        if payment_data and ("invoice_url" in payment_data or "id" in payment_data):
            # Success
            self._send_json(200, {
                "order_id": payment_data.get("order_id") or internal_order_id,
                "nowpayments": {
                    "invoice_url": payment_data.get("invoice_url"),
                    "payment_id": payment_data.get("id")
                },
                "amount": price,
                "currency": "USD",
                "status": "pending",
                "message": "Invoice created. Redirecting to payment..."
            })
        else:
            # Failure fallback
            self._send_json(500, {
                "error": "payment_creation_failed",
                "message": "Could not create payment invoice. Please try again later."
            })

    def handle_token(self, data):
        # Placeholder for token logic
        self._send_json(200, {"status": "token_issued"})

if __name__ == "__main__":
    from http.server import HTTPServer
    server = HTTPServer(('localhost', 5000), handler)
    print("Starting local server on http://localhost:5000")
    server.serve_forever()
