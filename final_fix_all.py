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

        # Calculate approx ETH (1 ETH ~ $1960 - Feb 2026 Market Rate)
        eth_price = price_usd / 1960.0
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
                # Group 1: Price ($XX.XX) - though we insert price_usd directly
                # Group 2: Inner content (span etc)
                replacement = f'<div class="price">${price_usd:.2f}\\2</div><div class="crypto-price-display" style="font-size: 0.8rem; color: #666; margin-top: 5px;">Pay with USDT, ETH (~{eth_str}), BTC</div>'
                new_content = re.sub(r'<div class="price">(\$\d+\.\d{2})(.*?)</div>', replacement, new_content, count=1)
            else:
                # Update existing clarification to ensure class and correct ETH amount
                # Match the old style div or new style div
                # We use a broad regex for the div content
                replacement = f'<div class="crypto-price-display" style="font-size: 0.8rem; color: #666; margin-top: 5px;">Pay with USDT, ETH (~{eth_str}), BTC</div>'
                
                # Regex for old div (without class)
                new_content = re.sub(
                    r'<div style="font-size: 0.8rem; color: #666; margin-top: 5px;">Pay with USDT, ETH \(~[\d\.]+\), BTC</div>', 
                    replacement, 
                    new_content
                )
                
                # Regex for new div (with class) - just update amount
                new_content = re.sub(
                    r'<div class="crypto-price-display" style="font-size: 0.8rem; color: #666; margin-top: 5px;">Pay with USDT, ETH \(~[\d\.]+\), BTC</div>', 
                    replacement, 
                    new_content
                )

            # 7. Inject Dynamic Price Script (CoinGecko)
            if "updateEthPrice" not in new_content:
                script_content = """
<script>
  (function() {
    function updateEthPrice() {
      var priceEl = document.querySelector('.price');
      if (!priceEl) return;
      var priceText = priceEl.childNodes[0].textContent.replace(/[^0-9.]/g, '');
      var price = parseFloat(priceText);
      if (isNaN(price)) price = 49.00;
      
      fetch('https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd')
        .then(function(res) { return res.json(); })
        .then(function(data) {
          var ethRate = data.ethereum.usd;
          var ethAmount = (price / ethRate).toFixed(4);
          
          // Try to update via class
          var cryptoEl = document.querySelector('.crypto-price-display');
          if (cryptoEl) {
             cryptoEl.innerHTML = 'Pay with USDT, ETH (~' + ethAmount + '), BTC';
          } else {
             // Fallback to text search
             var els = document.querySelectorAll('div');
             for (var i = 0; i < els.length; i++) {
                if (els[i].textContent.indexOf('Pay with USDT, ETH') > -1) {
                   els[i].innerHTML = 'Pay with USDT, ETH (~' + ethAmount + '), BTC';
                   break;
                }
             }
          }
        })
        .catch(function(err) {
           console.log('ETH price fetch failed, using fallback');
        });
    }
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', updateEthPrice);
    } else {
      updateEthPrice();
    }
  })();
</script>
"""
                new_content = new_content.replace("</body>", script_content + "\n</body>")

            # 8. Inject Refund Policy if missing
            refund_text = "Refund Policy: Due to the nature of digital products, all sales are final. No refunds are available after download."
            faq_card = '<div class="card"><h4>Refund Policy</h4><p>Due to the nature of digital products, all sales are final. No refunds are available after download.</p></div>'
            
            if "Refund Policy" not in new_content:
                # Strategy 1: Inject into FAQ section (Best UX)
                if '<div class="faq">' in new_content:
                    parts = new_content.split('<div class="faq">')
                    if len(parts) > 1:
                        if '</section>' in parts[1]:
                            subparts = parts[1].split('</section>', 1)
                            # Try to inject inside .faq div
                            if '</div>' in subparts[0]:
                                div_parts = subparts[0].rsplit('</div>', 1)
                                new_faq_inner = div_parts[0] + f'\n{faq_card}\n' + '</div>' + div_parts[1]
                                new_content = parts[0] + '<div class="faq">' + new_faq_inner + '</section>' + subparts[1]
                                print(f"[{product_id}] Injected Refund Policy INSIDE .faq div.")
                            else:
                                # Append before section end
                                new_content = parts[0] + '<div class="faq">' + subparts[0] + f'\n{faq_card}\n' + '</section>' + subparts[1]
                                print(f"[{product_id}] Injected Refund Policy at end of FAQ section.")

                # Fallback strategies if FAQ injection failed
                if new_content == content:
                     refund_div = f'<div style="text-align: center; padding: 20px; color: #666; font-size: 0.9rem; max-width: 800px; margin: 0 auto;">{refund_text}</div>'
                     # Strategy 2: Inject before footer
                     if re.search(r'<footer', new_content, re.IGNORECASE):
                         new_content = re.sub(r'(<footer)', f'{refund_div}\n\\1', new_content, count=1, flags=re.IGNORECASE)
                         print(f"[{product_id}] Injected Refund Policy before footer.")
                     # Strategy 3: Inject before </body>
                     else:
                         new_content = new_content.replace('</body>', f'{refund_div}\n</body>')
                         print(f"[{product_id}] Injected Refund Policy before </body>.")

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
