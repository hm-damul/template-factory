from flask import Flask, render_template
from src.ledger_manager import LedgerManager
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

app = Flask(__name__)

def test_render():
    lm = LedgerManager()
    product_id = "20260220-211248-digital-asset-bundle-2026-02-2"
    product = lm.get_product(product_id)
    
    if not product:
        print("Product not found")
        return

    if not product.get("metadata"):
        product["metadata"] = {}
        
    print(f"Product: {product.keys()}")
    print(f"Metadata: {product['metadata']}")

    with app.app_context():
        try:
            # We need to make sure templates folder is found
            print(f"Template folder: {app.template_folder}")
            rendered = render_template("checkout.html", product=product)
            print("Render SUCCESS")
            print(rendered[:100])
        except Exception as e:
            print(f"Render FAILED: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_render()
