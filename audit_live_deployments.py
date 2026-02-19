import sys
import requests
import time
from pathlib import Path
from typing import List, Dict, Any

# Root Path
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.append(str(PROJECT_ROOT))

from src.ledger_manager import LedgerManager
from src.config import Config

def audit_deployments():
    lm = LedgerManager(Config.DATABASE_URL)
    # Check both PUBLISHED and PROMOTED
    products = lm.get_products_by_status("PUBLISHED") + lm.get_products_by_status("PROMOTED")
    
    print(f"Auditing {len(products)} products (PUBLISHED + PROMOTED)...")
    
    results = []
    
    for p in products:
        pid = p["id"]
        meta = p.get("metadata", {})
        url = meta.get("deployment_url", "")
        
        res = {
            "id": pid,
            "url": url,
            "status": "UNKNOWN",
            "reason": ""
        }
        
        if not url:
            res["status"] = "MISSING_URL"
            res["reason"] = "No deployment URL found in metadata"
            results.append(res)
            print(f"[{pid}] MISSING URL")
            continue
            
        try:
            # Check if URL is valid
            if not url.startswith("http"):
                url = "https://" + url
                
            resp = requests.get(url, timeout=10)
            
            if resp.status_code == 200:
                content = resp.text.lower()
                if "deployment has failed" in content:
                    res["status"] = "FAILED_CONTENT"
                    res["reason"] = "Vercel error page detected"
                    lm.update_product_status(pid, "DEPLOYMENT_FAILED")
                    print(f"[{pid}] FAILED (Vercel Error Page)")
                elif "404: not found" in content:
                     res["status"] = "FAILED_404"
                     res["reason"] = "404 Not Found detected"
                     lm.update_product_status(pid, "DEPLOYMENT_FAILED")
                     print(f"[{pid}] FAILED (404 Content)")
                else:
                    # Check API Health
                    api_url = url.rstrip("/") + "/api/health"
                    try:
                        api_resp = requests.get(api_url, timeout=5)
                        if api_resp.status_code == 200:
                            # Verify it's JSON, not source code
                            try:
                                data = api_resp.json()
                                if data.get("ok") is True:
                                    res["status"] = "OK"
                                    print(f"[{pid}] OK (API Verified: JSON)")
                                else:
                                    res["status"] = "API_BAD_RESPONSE"
                                    res["reason"] = f"API returned unexpected JSON: {data}"
                                    print(f"[{pid}] API BAD JSON")
                            except ValueError:
                                # Not JSON -> Likely source code (Static File)
                                res["status"] = "API_STATIC_FILE"
                                res["reason"] = "API returned non-JSON (likely source code)"
                                lm.update_product_status(pid, "DEPLOYMENT_FAILED")
                                print(f"[{pid}] FAILED (API is Static File)")
                        else:
                            res["status"] = "API_FAILED"
                            res["reason"] = f"API Health check failed: {api_resp.status_code}"
                            # Don't mark as FAILED in DB yet, just report
                            print(f"[{pid}] API FAILED ({api_resp.status_code})")
                    except Exception as e:
                        res["status"] = "API_ERROR"
                        res["reason"] = f"API check error: {e}"
                        print(f"[{pid}] API ERROR ({e})")
            else:
                res["status"] = "HTTP_ERROR"
                res["reason"] = f"HTTP {resp.status_code}"
                lm.update_product_status(pid, "DEPLOYMENT_FAILED")
                print(f"[{pid}] HTTP {resp.status_code}")
                
        except Exception as e:
            res["status"] = "CONNECTION_ERROR"
            res["reason"] = str(e)
            print(f"[{pid}] ERROR: {e}")
            
        results.append(res)
        time.sleep(0.5) # Rate limit protection
        
    # Summary
    ok_count = sum(1 for r in results if r["status"] == "OK")
    failed_count = len(results) - ok_count
    
    print("\n" + "="*50)
    print(f"AUDIT COMPLETE: {ok_count} OK, {failed_count} FAILED")
    print("="*50)
    
    for r in results:
        if r["status"] != "OK":
            print(f"{r['id']} | {r['status']} | {r['reason']} | {r['url']}")

if __name__ == "__main__":
    audit_deployments()
