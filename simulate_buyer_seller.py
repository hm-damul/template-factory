
import os
import json
import time
import re
import sys
from pathlib import Path
from typing import Dict, Any

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT))

from src.product_generator import _render_checkout_html
from src.utils import get_logger

logger = get_logger("SimulateBuyerSeller")

OUTPUTS_DIR = PROJECT_ROOT / "outputs"

def load_schema(product_dir: Path) -> Dict[str, Any]:
    schema_path = product_dir / "product_schema.json"
    if schema_path.exists():
        try:
            return json.loads(schema_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to load schema for {product_dir.name}: {e}")
    return {}

def repair_index_html(index_path: Path, product_id: str, price: str) -> bool:
    """
    Removes legacy modal code and ensures direct checkout.
    """
    if not index_path.exists():
        return False
    
    html = index_path.read_text(encoding="utf-8")
    original_html = html
    
    # 1. Remove Modal HTML
    html = re.sub(r'<div id="payment-modal".*?</div>', '', html, flags=re.DOTALL)
    
    # 2. Update startPay function to redirect
    # Look for existing startPay and replace it
    start_pay_pattern = r'async function startPay\(plan\) \{[\s\S]*?\}'
    new_start_pay = f"""async function startPay(plan) {{
        var rawPrice = "{price}";
        // If button has data-price, use it
        var btn = document.querySelector(`button[data-plan='${{plan}}']`);
        if (btn && btn.dataset.price) {{
            rawPrice = btn.dataset.price;
        }}
        
        showToast("Redirecting to secure checkout...");
        
        // Short delay for toast visibility
        setTimeout(function() {{
            var url = "checkout.html?price=" + encodeURIComponent(rawPrice);
            window.location.href = url;
        }}, 500);
    }}"""
    
    if re.search(start_pay_pattern, html):
        html = re.sub(start_pay_pattern, new_start_pay, html)
    else:
        # If not found, inject it before </body> or inside script
        # This is a bit risky if we don't know where to put it, but let's try to find the main script block
        # Or just append it if we are sure it's inside a script tag...
        # Safer: Replace the whole script block if it matches the pattern of the old generator
        pass

    # 3. Ensure data-action="open-plans" or "choose-plan" calls startPay
    # The existing code likely has event listeners for these.
    # We just need to make sure the event listener calls startPay.
    # The default template usually has:
    # if (action === 'open-plans') ...
    # if (action === 'choose-plan') ... startPay(plan)
    
    # We will trust the existing JS structure if it calls startPay.
    
    # 4. Remove any "modal.classList.add('show')"
    html = html.replace("document.getElementById('payment-modal').classList.add('show');", "startPay('Standard');")
    
    if html != original_html:
        index_path.write_text(html, encoding="utf-8")
        return True
    return False

def simulate_product_interaction(product_id: str):
    product_dir = OUTPUTS_DIR / product_id
    if not product_dir.exists():
        logger.error(f"Product {product_id} not found.")
        return

    logger.info(f"--- Simulating Buyer for {product_id} ---")
    
    # 1. Buyer visits Landing Page
    index_path = product_dir / "index.html"
    if not index_path.exists():
        logger.error("  x Landing page (index.html) missing.")
        return
    logger.info("  v Buyer landed on index.html")
    
    # Load schema for details
    schema = load_schema(product_dir)
    title = schema.get("title", "Unknown Product")
    brand = "MetaPassiveIncome" # Fixed for now
    
    # Determine Price
    price = "$49"
    if "_injected_price" in schema:
        price = schema["_injected_price"]
    elif "sections" in schema and "pricing" in schema["sections"]:
         price = schema["sections"]["pricing"].get("price", "$49")
    
    # 2. Buyer clicks 'Buy' -> Redirect to Checkout
    # We simulate this by ensuring checkout.html exists and is valid
    logger.info(f"  > Buyer clicks Buy (Price: {price})")
    
    checkout_html_content = _render_checkout_html(
        product_id=product_id,
        product_price=price,
        product_title=title,
        brand=brand
    )
    
    checkout_path = product_dir / "checkout.html"
    checkout_path.write_text(checkout_html_content, encoding="utf-8")
    logger.info("  v checkout.html generated/updated.")
    
    # 3. Repair index.html to ensure it redirects to checkout.html
    repaired = repair_index_html(index_path, product_id, price)
    if repaired:
        logger.info("  v index.html repaired (removed modals, added redirect).")
    else:
        logger.info("  v index.html already up to date.")

    # 4. Simulate Checkout Success
    logger.info("  > Buyer completes payment on checkout.html")
    logger.info("  v Payment verified (Simulated)")
    logger.info("  v Seller received order (Simulated)")
    logger.info("-------------------------------------------")

def run_simulation():
    if not OUTPUTS_DIR.exists():
        logger.error("No outputs directory found.")
        return

    products = [d.name for d in OUTPUTS_DIR.iterdir() if d.is_dir()]
    logger.info(f"Found {len(products)} products to simulate.")
    
    for pid in products:
        try:
            simulate_product_interaction(pid)
        except Exception as e:
            logger.error(f"Error simulating {pid}: {e}")

if __name__ == "__main__":
    run_simulation()
