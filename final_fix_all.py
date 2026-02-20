import os
import sys
import glob
import json
import re
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.append(str(PROJECT_ROOT))

from src.ledger_manager import LedgerManager
from add_comparison_table import inject_comparison
from regenerate_promos_fixed import regenerate_all_promotions_strict
from generate_catalog import main as generate_catalog_main

def update_product_pages_price():
    """
    Iterates over all product pages (index.html) and ensures the displayed price
    matches the product_schema.json price.
    Also injects crypto clarification.
    """
    print("--- Updating Product Pages (index.html) Prices ---")
    outputs_dir = PROJECT_ROOT / "outputs"
    if not outputs_dir.exists():
        print("outputs directory not found.")
        return

    count = 0
    for p_dir in outputs_dir.iterdir():
        if not p_dir.is_dir():
            continue
            
        product_id = p_dir.name
        schema_path = p_dir / "product_schema.json"
        index_path = p_dir / "index.html"
        
        if not schema_path.exists() or not index_path.exists():
            continue
            
        # Get correct price from schema
        price_usd = 49.00 # Default fallback
        try:
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema = json.load(f)
                
                # Priority 1: "pricing" section
                p_str = schema.get("sections", {}).get("pricing", {}).get("price", "")
                if p_str:
                    price_usd = float(str(p_str).replace("$", "").replace(",", ""))
                
                # Priority 2: "market_analysis"
                elif "market_analysis" in schema:
                     p_val = schema["market_analysis"].get("our_price")
                     if p_val:
                         price_usd = float(p_val)
                
                # Priority 3: root "price"
                elif "price" in schema:
                    price_usd = float(str(schema["price"]).replace("$", ""))

        except Exception as e:
            print(f"[{product_id}] Error reading schema: {e}. Using default ${price_usd}")

        # Calculate approx ETH (1 ETH ~ $2500)
        eth_price = price_usd / 2500.0
        eth_str = f"{eth_price:.4f}"

        # Update manifest.json if exists
        manifest_path = p_dir / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                
                changed = False
                if manifest.get("price_usd") != price_usd:
                    manifest["price_usd"] = price_usd
                    changed = True
                
                if "metadata" in manifest and manifest["metadata"].get("price_usd") != price_usd:
                    manifest["metadata"]["price_usd"] = price_usd
                    changed = True
                    
                if "product" in manifest and manifest["product"].get("price_usd") != price_usd:
                    manifest["product"]["price_usd"] = price_usd
                    changed = True
                    
                if changed:
                    with open(manifest_path, 'w', encoding='utf-8') as f:
                        json.dump(manifest, f, indent=2)
                    print(f"[{product_id}] Updated manifest.json price to ${price_usd}")
            except Exception as e:
                print(f"[{product_id}] Error updating manifest: {e}")
            
        # Read index.html
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            new_content = content
            
            # 1. Update <div class="price">$XX.XX...</div>
            # We match the start of the div, the price, any content inside (like spans), and the closing div
            # Group 1: $XX.XX
            # Group 2: remaining content inside div
            new_content = re.sub(
                r'<div class="price">(\$\d+\.\d{2})(.*?)</div>', 
                f'<div class="price">${price_usd:.2f}\\2</div>', 
                new_content
            )
            
            # 2. Update data-price="$XX.XX"
            new_content = re.sub(r'data-price="\$\d+\.\d{2}"', f'data-price="${price_usd:.2f}"', new_content)
            
            # 3. Update schema "price": "XX.XX"
            new_content = re.sub(r'"price": "\d+\.\d{2}"', f'"price": "{price_usd:.2f}"', new_content)

            # 4. Fix hardcoded script prices: Standard License ($49.00)
            new_content = re.sub(r'Standard License \(\$\d+\.\d{2}\)', f'Standard License (${price_usd:.2f})', new_content)
            
            # 5. Fix fallback price in JS: || "$19"
            new_content = re.sub(r'\|\| "\$\d+"', f'|| "${price_usd:.0f}"', new_content)
            
            # 6. Inject Crypto clarification
            # Look for the price div and append text if not already there
            marker = "Pay with USDT, ETH"
            if marker not in new_content:
                # Inject after the price div (accounting for potential spans inside)
                replacement = f'<div class="price">${price_usd:.2f}\\2</div><div style="font-size: 0.8rem; color: #666; margin-top: 5px;">Pay with USDT, ETH (~{eth_str}), BTC</div>'
                new_content = re.sub(r'<div class="price">\$\d+\.\d{2}(.*?)</div>', replacement, new_content, count=1)
            else:
                # Update existing clarification if price/ETH changed
                # Use regex to replace the ETH amount
                new_content = re.sub(r'Pay with USDT, ETH \(~[\d\.]+\)', f'Pay with USDT, ETH (~{eth_str})', new_content)

            if new_content != content:
                with open(index_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"[{product_id}] Updated prices in index.html to ${price_usd:.2f} (~{eth_str} ETH)")
                count += 1
                
        except Exception as e:
            print(f"[{product_id}] Error updating index.html: {e}")

    print(f"Updated prices in {count} product pages.")

def main():
    # 1. Update index.html prices (Card, Schema, Data attributes)
    update_product_pages_price()
    
    # 2. Inject/Update Comparison Tables (Text-based, using Schema price)
    print("\n--- Injecting/Updating Comparison Tables ---")
    inject_comparison()
    
    # 3. Regenerate Promotions (Blog, Social, etc.) using Schema price
    print("\n--- Regenerating Promotions ---")
    regenerate_all_promotions_strict()
    
    # 4. Regenerate Catalog (Main Index)
    print("\n--- Regenerating Catalog ---")
    generate_catalog_main()
    
    print("\n=== ALL TASKS COMPLETED ===")

if __name__ == "__main__":
    main()
