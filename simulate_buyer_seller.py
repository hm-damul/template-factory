
import os
import json
import time
import re
import sys
from pathlib import Path
from typing import Dict, Any
from bs4 import BeautifulSoup

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT))

# Use absolute import if possible, or relative if package structure allows
try:
    from src.product_generator import _render_checkout_html
except ImportError:
    # Fallback if running as script
    sys.path.append(str(PROJECT_ROOT / "src"))
    from product_generator import _render_checkout_html

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
    Removes legacy modal code and ensures direct checkout using BeautifulSoup.
    """
    if not index_path.exists():
        return False
    
    html_content = index_path.read_text(encoding="utf-8")
    original_html = html_content
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. Remove Modal Elements
    # Remove by class 'modal-backdrop'
    for div in soup.find_all("div", class_="modal-backdrop"):
        div.decompose()
        
    # Remove by ID 'modal-login', 'modal-plans'
    for modal_id in ["modal-login", "modal-plans"]:
        modal = soup.find(id=modal_id)
        if modal:
            modal.decompose()
            
    # Remove comments (optional, but good for cleanup)
    # BeautifulSoup doesn't remove comments by default easily without iteration, skipping for now.

    # 2. Update JS Logic (Regex still needed for script content)
    # We get the string back from soup
    html = str(soup)
    
    # 2.1 Update startPay function
    # Matches async function startPay(plan) { ... }
    # We replace it with the direct checkout version
    
    # We use a unique key based on product_id if available in JS context, 
    # but here we hardcode the key pattern to match what generator_module uses.
    
    new_start_pay = f"""async function startPay(plan) {{
        var rawPrice = "{price}";
        // Try to find price from local storage
        // The key variable might be defined as KEY_PRICE, or we can reconstruct it
        var key = "{product_id}:price";
        var stored = localStorage.getItem(key);
        if (stored) rawPrice = stored;
        
        // Also check if button has data-price (if clicked)
        // This is harder inside startPay without the event, but localStorage is reliable if set by choose-plan
        
        showToast("Redirecting to secure checkout...");
        setTimeout(function() {{
            var url = "checkout.html?price=" + encodeURIComponent(rawPrice);
            window.location.href = url;
        }}, 500);
    }}"""
    
    # Regex to replace existing startPay
    start_pay_pattern = r'async function startPay\(plan\)\s*\{[\s\S]*?\}'
    if re.search(start_pay_pattern, html):
        html = re.sub(start_pay_pattern, new_start_pay, html)
        
    # 2.2 Patch 'actions' object
    # open-login -> startPay("SignIn")
    html = re.sub(
        r'"open-login":\s*function\(\)\s*\{[\s\S]*?\},',
        r'"open-login": function() { startPay("SignIn"); },',
        html
    )
    
    # open-plans -> startPay(plan)
    # Matches: "open-plans": function() { ... },
    html = re.sub(
        r'"open-plans":\s*function\(\)\s*\{[\s\S]*?\},',
        r'''"open-plans": function() { 
          var plan = localStorage.getItem("''' + product_id + ''':plan") || "Premium";
          startPay(plan); 
        },''',
        html
    )

    # choose-plan -> set storage and startPay
    # Matches: "choose-plan": function(el) { ... },
    choose_plan_new = r'''"choose-plan": function(el) {
          var plan = el.getAttribute("data-plan") || "Starter";
          var price = el.getAttribute("data-price") || "''' + price + '''";
          localStorage.setItem("''' + product_id + ''':plan", plan);
          localStorage.setItem("''' + product_id + ''':price", price);
          showToast("Plan selected: " + plan + " (" + price + ")");
          startPay(plan);
        },'''
        
    html = re.sub(
        r'"choose-plan":\s*function\(el\)\s*\{[\s\S]*?\},',
        choose_plan_new,
        html
    )

    # 3. Remove CSS for modals if possible (Regex)
    # .modal-backdrop { ... }
    html = re.sub(r'\.modal-backdrop\s*\{[\s\S]*?\}', '', html)
    html = re.sub(r'\.modal\s*\{[\s\S]*?\}', '', html)
    html = re.sub(r'\.modal\.show\s*\{[\s\S]*?\}', '', html)

    if html != original_html:
        index_path.write_text(html, encoding="utf-8")
        return True
    return False

def simulate_product_interaction(product_id: str):
    product_dir = OUTPUTS_DIR / product_id
    if not product_dir.exists():
        logger.error(f"Product {product_id} not found.")
        return

    logger.info(f"--- Processing {product_id} ---")
    
    # 1. Check Index
    index_path = product_dir / "index.html"
    if not index_path.exists():
        logger.error("  x Landing page (index.html) missing.")
        return
    
    # Load schema for details
    schema = load_schema(product_dir)
    title = schema.get("title", "Unknown Product")
    brand = "MetaPassiveIncome"
    
    # Determine Price
    price = "$49"
    if "_injected_price" in schema:
        price = schema["_injected_price"]
    elif "sections" in schema and "pricing" in schema["sections"]:
         price = schema["sections"]["pricing"].get("price", "$49")
    
    # 2. Generate/Update checkout.html
    # Always regenerate to ensure it matches the latest logic/price
    checkout_html_content = _render_checkout_html(
        product_id=product_id,
        product_price=price,
        product_title=title,
        brand=brand
    )
    
    checkout_path = product_dir / "checkout.html"
    checkout_path.write_text(checkout_html_content, encoding="utf-8")
    logger.info(f"  v checkout.html generated/updated (Price: {price})")
    
    # 3. Repair index.html
    repaired = repair_index_html(index_path, product_id, price)
    if repaired:
        logger.info("  v index.html patched (Modals removed, Direct Checkout enforced).")
    else:
        logger.info("  . index.html clean/already patched.")

def run_simulation():
    if not OUTPUTS_DIR.exists():
        logger.error("No outputs directory found.")
        return

    products = [d.name for d in OUTPUTS_DIR.iterdir() if d.is_dir()]
    logger.info(f"Found {len(products)} products.")
    
    for pid in products:
        try:
            simulate_product_interaction(pid)
        except Exception as e:
            logger.error(f"Error processing {pid}: {e}")

if __name__ == "__main__":
    run_simulation()
