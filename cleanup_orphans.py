
import os
import shutil
import subprocess
from src.ledger_manager import LedgerManager

def main():
    lm = LedgerManager()
    products = lm.list_products()
    product_ids = set(p['id'] for p in products)
    
    if os.path.exists("outputs"):
        output_dirs = [d for d in os.listdir("outputs") if os.path.isdir(os.path.join("outputs", d))]
        orphan_dirs = [d for d in output_dirs if d not in product_ids]
        
        print(f"Found {len(orphan_dirs)} orphan output directories.")
        
        for d in orphan_dirs:
            path = os.path.join("outputs", d)
            print(f"Deleting orphan: {path}")
            try:
                # Remove from git first if tracked
                subprocess.run(["git", "rm", "-r", "-f", path], capture_output=True)
                # Remove from disk if still exists
                if os.path.exists(path):
                    shutil.rmtree(path)
            except Exception as e:
                print(f"Error deleting {path}: {e}")
                
    # Also clean up public/outputs orphans
    if os.path.exists("public/outputs"):
        public_dirs = [d for d in os.listdir("public/outputs") if os.path.isdir(os.path.join("public/outputs", d))]
        orphan_public = [d for d in public_dirs if d not in product_ids]
        
        print(f"Found {len(orphan_public)} orphan public output directories.")
        
        for d in orphan_public:
            path = os.path.join("public/outputs", d)
            print(f"Deleting public orphan: {path}")
            try:
                subprocess.run(["git", "rm", "-r", "-f", path], capture_output=True)
                if os.path.exists(path):
                    shutil.rmtree(path)
            except Exception as e:
                print(f"Error deleting {path}: {e}")

    # Commit changes
    try:
        subprocess.run(["git", "commit", "-m", "Cleanup orphan output directories"], check=False)
        subprocess.run(["git", "push"], check=False) # Push deletion
    except Exception as e:
        print(f"Git commit/push failed: {e}")

if __name__ == "__main__":
    main()
