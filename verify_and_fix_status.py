import sys
import json
import requests
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Import from src package
try:
    from src.ledger_manager import LedgerManager
except ImportError:
    # Fallback if src is not a package
    sys.path.append(str(ROOT / "src"))
    from ledger_manager import LedgerManager

def verify_and_fix():
    print("Initializing LedgerManager...")
    lm = LedgerManager()
    products = lm.get_all_products()
    
    print(f"Checking {len(products)} products for stale PUBLISH_FAILED status...")
    
    fixed_count = 0
    
    for p in products:
        status = p.get("status")
        if status == "PUBLISH_FAILED":
            pid = p["id"]
            meta = p.get("metadata", {})
            url = meta.get("deployment_url")
            
            # Construct URL if missing
            if not url:
                url = f"https://metapassiveincome-final.vercel.app/outputs/{pid}/index.html"
                print(f"[{pid}] No URL in metadata. Trying constructed URL: {url}")
            
            print(f"[{pid}] Verifying URL: {url}")
            
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    print(f"[{pid}] URL is accessible! Updating status to PUBLISHED.")
                    
                    # Determine new status based on promotions
                    has_promo = (
                        meta.get("wp_link") or 
                        meta.get("medium_url") or 
                        meta.get("x_post_id") or
                        p.get("promotions") # Some versions store here
                    )
                    new_status = "PROMOTED" if has_promo else "PUBLISHED"
                    
                    # Update metadata
                    meta["deployment_url"] = url
                    meta["error"] = None 
                    
                    # Use update_product_status
                    lm.update_product_status(pid, new_status, metadata=meta)
                    fixed_count += 1
                else:
                    print(f"[{pid}] URL verification failed: {resp.status_code}")
            except Exception as e:
                print(f"[{pid}] Verification error: {e}")
                
    print(f"Fixed {fixed_count} products.")

if __name__ == "__main__":
    verify_and_fix()
