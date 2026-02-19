
import os
import sys
import glob
import re
import json
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.append(str(PROJECT_ROOT))

from src.ledger_manager import LedgerManager
from src.config import Config
from monetize_module import MonetizeModule, PaymentInjectConfig

def update_prices():
    lm = LedgerManager(Config.DATABASE_URL)
    mm = MonetizeModule()
    
    files = glob.glob("outputs/*/index.html")
    print(f"Found {len(files)} index.html files.")
    
    count = 0
    for file_path in files:
        path_obj = Path(file_path)
        product_id = path_obj.parent.name
        
        # Get price from ledger
        price_usd = 19.9
        p_info = lm.get_product(product_id)
        if p_info:
            meta = p_info.get("metadata", {})
            if isinstance(meta, str):
                try: meta = json.loads(meta)
                except: meta = {}
            price_usd = float(meta.get("final_price_usd", 19.9))
        
        print(f"[{product_id}] Updating price to ${price_usd}...")
        
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # 1. Remove old injected widget
        pattern = r'<!-- ======= PAYMENT WIDGET \(injected\) ======= -->.*?<script>.*?</script>'
        new_content = re.sub(pattern, "", content, flags=re.DOTALL)
        
        # Fallback manual removal
        if len(new_content) == len(content):
            if 'id="catp-pay"' in content:
                 start_marker = '<!-- ======= PAYMENT WIDGET (injected) ======= -->'
                 idx_start = content.find(start_marker)
                 if idx_start != -1:
                     idx_end = content.find('</script>', idx_start)
                     if idx_end != -1:
                         new_content = content[:idx_start] + content[idx_end+9:]
                         print(f"  -> Removed old widget (manual slice).")

        # 2. Update Template Prices (data-price and visual price)
        price_str = f"${price_usd:.2f}"
        
        # Replace data-price="..."
        def replace_price_attr(match):
            return f'data-price="{price_str}"'
        new_content = re.sub(r'data-price="\$?[\d.]+"', replace_price_attr, new_content)
        
        # Replace visual price
        new_content = re.sub(r'<div class="price">\$[\d.]+(<span)', f'<div class="price">{price_str}\\1', new_content)
        
        # 3. FIX: isLocalPreview logic (allow port 8090)
        # Original: if (p === "8090") return false;
        # New: // if (p === "8090") return false;
        if 'if (p === "8090") return false;' in new_content:
            new_content = new_content.replace('if (p === "8090") return false;', '// if (p === "8090") return false;')
            print("  -> Fixed isLocalPreview logic (enabled 8090).")

        # 4. FIX: Use startCryptoPay instead of startPay
        # Original: onclick="startPay(this.dataset.plan)" or similar
        # New: onclick="startCryptoPay(this.dataset.price || this.getAttribute('data-price'))"
        # We replace any onclick="startPay(...)" with the new call
        if 'onclick="startPay' in new_content:
            new_content = re.sub(
                r'onclick="startPay\([^)]*\)"', 
                r'onclick="startCryptoPay(this.dataset.price || this.getAttribute(\'data-price\'))"', 
                new_content
            )
            print("  -> Replaced startPay with startCryptoPay.")

        # Write back (intermediate save)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
            
        # 5. Inject new widget (with updated monetize_module.py logic)
        try:
            mm.inject_payment_logic(
                target_html_path=file_path,
                config=PaymentInjectConfig(product_id=product_id, price_usd=price_usd)
            )
            print(f"  -> Injected new widget with price ${price_usd}.")
            count += 1
        except Exception as e:
            print(f"  -> Injection failed: {e}")

    print(f"Updated {count} files.")

if __name__ == "__main__":
    update_prices()
