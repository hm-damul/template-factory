import os
import sys
import sqlite3
import json
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Need to set up environment for imports
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

try:
    from promotion_dispatcher import build_channel_payloads
    from src.ledger_manager import LedgerManager
    from src.config import Config
except ImportError as e:
    print(f"Import Error: {e}")
    # Fallback for direct execution
    sys.path.append(os.getcwd())
    from promotion_dispatcher import build_channel_payloads
    from src.ledger_manager import LedgerManager
    from src.config import Config

def regenerate_all_promotions():
    print("Starting promotion regeneration...")
    
    # Connect to ledger
    db_path = Config.DATABASE_URL
    if "sqlite:///" in db_path:
        db_path = db_path.replace("sqlite:///", "")
    
    # Initialize LedgerManager
    lm = LedgerManager(Config.DATABASE_URL)
    products = lm.get_all_products()
    
    print(f"Found {len(products)} products in ledger.")
    
    count = 0
    updated = 0
    errors = 0
    
    for p in products:
        pid = p['id']
        topic = p['topic']
        
        # We only care about products that have been generated (have an output dir)
        output_dir = Path(f"outputs/{pid}")
        if not output_dir.exists():
            # print(f"Skipping {pid} (no output directory)")
            continue
            
        try:
            # Check current price in ledger
            meta = p.get('metadata')
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except:
                    meta = {}
            
            ledger_price = meta.get('price_usd')
            if not ledger_price:
                # Default to 179 if not set (as per user requirement/observation)
                ledger_price = 179
            
            ledger_price_float = float(ledger_price)
            
            # Check manifest.json
            manifest_path = output_dir / "manifest.json"
            if manifest_path.exists():
                try:
                    m_content = manifest_path.read_text(encoding="utf-8")
                    m = json.loads(m_content)
                    
                    # Check price in manifest
                    m_price = m.get("metadata", {}).get("price_usd") or m.get("product", {}).get("price_usd")
                    
                    need_update = False
                    if m_price is None or float(m_price) != ledger_price_float:
                        print(f"[{pid}] updating manifest price from {m_price} to {ledger_price_float}")
                        if "metadata" not in m: m["metadata"] = {}
                        m["metadata"]["price_usd"] = ledger_price_float
                        m["product"]["price_usd"] = ledger_price_float # Ensure both places have it
                        need_update = True
                        
                    if need_update:
                        manifest_path.write_text(json.dumps(m, indent=2), encoding="utf-8")
                except Exception as e:
                    print(f"Error updating manifest for {pid}: {e}")

            # Now regenerate promotions
            # This function reads from manifest (now updated) and generates HTML
            payloads = build_channel_payloads(pid)
            
            # Verify the HTML content for "Our Price"
            blog_html_path = output_dir / "promotions" / "blog_post.html"
            if blog_html_path.exists():
                content = blog_html_path.read_text(encoding="utf-8")
                # Simple check: does it contain the price?
                # The format in promotion_dispatcher is: <td class="wp-promo-highlight">${current_price:.2f}</td>
                expected_str = f">${ledger_price_float:.2f}"
                if expected_str in content:
                    # print(f"[{pid}] Verified price {expected_str} in HTML.")
                    pass
                else:
                    print(f"[{pid}] WARNING: Price {expected_str} not found in generated HTML.")
            
            updated += 1
            
        except Exception as e:
            print(f"Error processing {pid}: {e}")
            errors += 1
            
        count += 1
        if count % 10 == 0:
            print(f"Processed {count} products...")

    print(f"\nCompleted. Updated: {updated}, Errors: {errors}")

if __name__ == "__main__":
    regenerate_all_promotions()
