
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT))

from src.ledger_manager import LedgerManager
from src.publisher import Publisher

def verify_publish_logic():
    lm = LedgerManager()
    products = lm.list_products()
    
    if not products:
        print("No products found in ledger.")
        return

    # Pick the first product that is not yet published or just use the latest one
    target = products[-1]
    pid = target['id']
    print(f"Verifying publish for product: {pid} (Current Status: {target['status']})")

    # Manually update status to PACKAGED for testing
    print(f"Force updating status of {pid} to PACKAGED for testing...")
    lm.update_product_status(pid, status="PACKAGED")
    target['status'] = "PACKAGED"

    # We need a real directory for Publisher to work
    output_dir = PROJECT_ROOT / "outputs" / pid
    if not output_dir.exists():
        print(f"Output directory {output_dir} does not exist. Creating a dummy one for testing.")
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "index.html").write_text("<html><body>Test</body></html>")

    # Check if Vercel token is set
    from src.config import Config
    if not Config.VERCEL_API_TOKEN:
        print("SKIP: Vercel API token not set. Cannot perform real deployment.")
        # But we can still test the ledger update logic if we mock the deploy method
        return

    try:
        pub = Publisher(lm)
        print("Starting publication...")
        # Note: This will actually deploy to Vercel if the token is valid!
        result = pub.publish_product(pid, str(output_dir))
        print(f"Publication result: {result['status']}")
        if result['status'] == 'PUBLISHED':
            print(f"Deployment URL: {result.get('metadata', {}).get('deployment_url')}")
    except Exception as e:
        print(f"Publication failed: {e}")

if __name__ == "__main__":
    verify_publish_logic()
