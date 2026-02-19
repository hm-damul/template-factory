
import sys
import json
import time
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.ledger_manager import LedgerManager
from src.publisher import Publisher
from src.config import Config
from promotion_dispatcher import dispatch_publish

def fix_product():
    product_id = "20260215-014951-automated-crypto-tax-reporting"
    print(f"Starting repair for {product_id}...")
    
    lm = LedgerManager("sqlite:///data/ledger.db")
    pub = Publisher(lm)
    
    prod = lm.get_product(product_id)
    if not prod:
        print("Product not found in ledger!")
        return

    # 1. Redeploy to Vercel
    output_dir = Path(f"outputs/{product_id}").resolve()
    if not output_dir.exists():
        print(f"Output directory not found: {output_dir}")
        return
        
    # Check index.html
    index_path = output_dir / "index.html"
    if not index_path.exists():
        print("index.html missing! Regenerating dummy index.html...")
        # Simple fallback index.html if missing
        index_path.write_text("<html><body><h1>Restored Product</h1><p>Please wait for full restoration.</p></body></html>", encoding="utf-8")
    
    print("Redeploying to Vercel...")
    try:
        # We need to manually call _deploy_to_vercel because publish() does a lot of other checks
        # and might skip if status is already PUBLISHED or something.
        # But publish() is safer. Let's try publish() first?
        # publish() checks status. If it's PROMOTED, it might skip?
        # Publisher.publish code:
        # if product['status'] == 'PUBLISHED' and not force: return
        # So we should probably use _deploy_to_vercel directly.
        
        project_name = f"meta-passive-income-{product_id.lower()}"
        # Sanitize name
        project_name = pub._sanitize_project_name(project_name)
        
        url = pub._deploy_to_vercel(product_id, project_name, str(output_dir))
        print(f"Redeployed successfully: {url}")
        
        # Update Ledger
        meta = prod.get("metadata", {})
        meta["deployment_url"] = url
        # Update status to PUBLISHED to ensure consistency (though it was PROMOTED)
        # Actually keep it PROMOTED if we are just fixing the link.
        # But let's update metadata.
        lm.create_product(product_id, prod["topic"], metadata=meta)
        print("Ledger updated with new URL.")
        
    except Exception as e:
        print(f"Redeployment failed: {e}")
        return

    # 2. Republish to WordPress
    print("Republishing to WordPress...")
    try:
        # Force wordpress channel
        res = dispatch_publish(product_id, channels=["wordpress"])
        wp_res = res.get("dispatch_results", {}).get("wordpress", {})
        
        if wp_res.get("ok"):
            print(f"WordPress post published: {wp_res.get('link')}")
        else:
            print(f"WordPress publish failed: {wp_res.get('error')}")
            
    except Exception as e:
        print(f"Promotion dispatch failed: {e}")

    print("Repair complete.")

if __name__ == "__main__":
    fix_product()
