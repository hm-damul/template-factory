
import os
import sys
import json
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.publisher import Publisher
from src.ledger_manager import LedgerManager
from dotenv import load_dotenv

def load_secrets():
    secrets_path = project_root / "data" / "secrets.json"
    if secrets_path.exists():
        try:
            print(f"Loading secrets from {secrets_path}")
            data = json.loads(secrets_path.read_text(encoding="utf-8"))
            for k, v in data.items():
                if v and isinstance(v, str):
                    os.environ[k] = v
                    # Also print partial key for verification
                    if "KEY" in k or "TOKEN" in k or "SECRET" in k:
                        print(f"  Loaded {k}: {v[:4]}...")
                    else:
                        print(f"  Loaded {k}: {v}")
        except Exception as e:
            print(f"Error loading secrets: {e}")

    # Also load .env
    load_dotenv(project_root / ".env")

def redeploy(product_id):
    load_secrets()
    
    ledger = LedgerManager()
    publisher = Publisher(ledger)
    
    # Find build output dir
    build_dir = project_root / "outputs" / product_id
    if not build_dir.exists():
        print(f"Build directory not found: {build_dir}")
        return

    # Find project name
    # We can reuse the existing project name if we know it, or let publisher generate one.
    # To find existing name, we can check final_publish_info.json if it exists
    publish_info_path = build_dir / "final_publish_info.json"
    project_name = f"meta-passive-income-{product_id}" # Default fallback
    
    if publish_info_path.exists():
        try:
            info = json.loads(publish_info_path.read_text(encoding="utf-8"))
            if "vercel_url" in info:
                # url is usually project-name.vercel.app
                # but might be custom domain.
                # simpler: just use sanitized product id as name, which is what publisher does by default for new projects
                pass
            if "project_name" in info:
                 project_name = info["project_name"]
                 print(f"Found existing project name: {project_name}")
        except:
            pass
            
    # Sanitize name just in case
    project_name = publisher._sanitize_project_name(project_name)
    print(f"Deploying product {product_id} to project {project_name}")
    
    try:
        url = publisher._deploy_to_vercel(product_id, project_name, str(build_dir))
        print(f"Deployment successful! URL: {url}")
        
        # Verify payment endpoint
        print("Verifying payment endpoint...")
        import requests
        check_url = f"{url}/api/pay/check?order_id=test&product_id={product_id}"
        try:
            r = requests.get(check_url, timeout=10)
            print(f"Check URL: {check_url}")
            print(f"Status: {r.status_code}")
            print(f"Response: {r.text[:200]}")
        except Exception as e:
            print(f"Verification request failed: {e}")
            
    except Exception as e:
        print(f"Deployment failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    product_id = "20260215-212725-token-gated-content-revenue-au"
    redeploy(product_id)
