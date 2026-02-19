
import os
import json
import time
from pathlib import Path
from typing import List, Tuple
import base64

# Add project root to path
import sys
sys.path.append(os.getcwd())

from src.ledger_manager import LedgerManager
from deploy_module_vercel_api import deploy_static_files

PROJECT_ROOT = Path(os.getcwd())
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

def get_product_files(product_dir: Path) -> List[Tuple[str, bytes]]:
    """Recursively get all files in the product directory."""
    files = []
    for item in product_dir.rglob("*"):
        if item.is_file():
            # Skip large files or unnecessary ones if needed
            if item.name.endswith(".zip"):
                continue
            
            # Vercel expects relative paths
            rel_path = item.relative_to(product_dir).as_posix()
            try:
                content = item.read_bytes()
                files.append((rel_path, content))
            except Exception as e:
                print(f"Skipping {item}: {e}")
    return files

def redeploy_all():
    print("Starting re-deployment of all products...")
    
    lm = LedgerManager()
    products_deployed = 0
    
    if not OUTPUTS_DIR.exists():
        print("Outputs directory not found.")
        return

    # Get all product directories
    product_dirs = [d for d in OUTPUTS_DIR.iterdir() if d.is_dir()]
    
    print(f"Found {len(product_dirs)} directories in outputs/")
    
    log_file = open("redeploy.log", "a", encoding="utf-8")
    
    for product_dir in product_dirs:
        product_id = product_dir.name
        
        # Check if recently deployed (within last hour)
        publish_info_path = product_dir / "final_publish_info.json"
        if publish_info_path.exists():
            try:
                info = json.loads(publish_info_path.read_text(encoding="utf-8"))
                if info.get("deployed_at") and time.time() - info.get("deployed_at") < 3600:
                    print(f"Skipping {product_id}: Already deployed recently.")
                    continue
            except:
                pass

        # Basic validation
        if not (product_dir / "index.html").exists():
            print(f"Skipping {product_id}: No index.html")
            continue
            
        print(f"Deploying {product_id}...")
        log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Deploying {product_id}...\n")
        log_file.flush()
        
        try:
            files = get_product_files(product_dir)
            if not files:
                print(f"  No files to deploy for {product_id}")
                continue
                
            # Use product_id as project name (sanitize if needed)
            # Vercel project names must be lowercase, max 100 chars, alphanumeric/hyphens
            project_name = "mpi-" + product_id.lower().replace("_", "-")[:90]
            
            # Retry loop for rate limits
            while True:
                try:
                    url = deploy_static_files(project_name, files, production=True)
                    break
                except Exception as e:
                    if "429" in str(e) or "rate_limited" in str(e):
                        print(f"  Rate limit hit. Waiting 60 seconds...")
                        time.sleep(60)
                        continue
                    else:
                        raise e

            print(f"  Deployed to: {url}")
            
            # Update local files
            publish_info = {
                "url": url,
                "deployed_at": time.time(),
                "files_count": len(files)
            }
            
            (product_dir / "final_publish_info.json").write_text(json.dumps(publish_info, indent=2), encoding="utf-8")
            
            # Update manifest if exists
            manifest_path = product_dir / "manifest.json"
            if manifest_path.exists():
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest["deployment_url"] = url
                    manifest["status"] = "PUBLISHED" # Ensure status is PUBLISHED
                    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
                except:
                    pass
            
            # Update Ledger
            lm.update_product_status(product_id, "PUBLISHED", metadata={"deployment_url": url, "price": 59})
            
            products_deployed += 1
            
            # Sleep briefly to avoid rate limits
            time.sleep(1)
            
        except Exception as e:
            print(f"  Failed to deploy {product_id}: {e}")
            
    print(f"Deployment complete. Redeployed {products_deployed} products.")

if __name__ == "__main__":
    redeploy_all()
