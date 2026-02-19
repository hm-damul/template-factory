from http.server import BaseHTTPRequestHandler
import json
import sys
from pathlib import Path
import traceback

# Add project root to sys.path for Vercel
_root = str(Path(__file__).resolve().parents[1])
if _root not in sys.path:
    sys.path.insert(0, _root)

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            from api._vercel_common import _get_query_param
            from payment_api import download_for_order
            
            # Use self as request object for helpers
            request = self
            
            order_id = _get_query_param(request, "order_id")
            if order_id:
                order_id = order_id.strip()
            
            token = _get_query_param(request, "token")
            if token:
                token = token.strip()
            
            if not order_id or not token:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"error": "missing_params"}')
                return

            project_root = Path(__file__).resolve().parents[1]
            info = download_for_order(project_root=project_root, order_id=order_id, token=token)
            
            if not info.get("ok"):
                status = int(info.get("status", 400))
                self.send_response(status)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(info).encode('utf-8'))
                return

            # Success - Serve File
            p = Path(str(info["package_path"]))
            if not p.exists():
                 self.send_response(404)
                 self.send_header('Content-type', 'application/json')
                 self.end_headers()
                 self.wfile.write(b'{"error": "file_not_found_on_server"}')
                 return
                 
            data = p.read_bytes()
            
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="{info.get("filename") or "package.zip"}"')
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            err_msg = f"INTERNAL_ERROR: {type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            print(f"[CRITICAL_ERROR] {err_msg}")
            self.wfile.write(json.dumps({"error": err_msg}).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
