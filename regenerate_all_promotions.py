import os
import sys
import json
import sqlite3
import random
from pathlib import Path

# Add project root and src to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
sys.path.append(os.path.join(current_dir, "src"))

try:
    from src.config import Config
    from promotion_dispatcher import build_channel_payloads
except ImportError as e:
    print(f"Import Error: {e}")
    # Fallback if src is not in path or Config fails
    class Config:
        DATABASE_URL = f"sqlite:///{os.path.join(current_dir, 'data', 'ledger.db')}"
        OUTPUT_DIR = os.path.join(current_dir, "outputs")

def get_ledger_products():
    db_url = Config.DATABASE_URL
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
    else:
        db_path = db_url
        
    if not os.path.exists(db_path):
        print(f"Ledger DB not found at {db_path}")
        return []
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, status, metadata_json FROM products")
        rows = cursor.fetchall()
        products = []
        for row in rows:
            # Handle different column names if needed
            if 'metadata_json' in row.keys():
                meta_raw = row['metadata_json']
            elif 'metadata' in row.keys():
                meta_raw = row['metadata']
            else:
                meta_raw = "{}"
                
            meta = json.loads(meta_raw) if meta_raw else {}
            
            price = meta.get('price_usd')
            if price is None:
                price = meta.get('final_price_usd')
                
            products.append({
                'id': row['id'],
                'status': row['status'],
                'price': price,
                'title': meta.get('title')
            })
        return products
    except Exception as e:
        print(f"Error reading ledger: {e}")
        return []
    finally:
        conn.close()

def update_manifest(product_id, ledger_price):
    manifest_path = os.path.join(Config.OUTPUT_DIR, product_id, "manifest.json")
    if not os.path.exists(manifest_path):
        print(f"[{product_id}] Manifest not found at {manifest_path}")
        return False

    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        
        updated = False
        
        # Check and update metadata.price_usd
        meta_price = manifest.get("metadata", {}).get("price_usd")
        if meta_price is None or float(meta_price) != float(ledger_price):
            print(f"[{product_id}] Updating manifest metadata price: {meta_price} -> {ledger_price}")
            if "metadata" not in manifest: manifest["metadata"] = {}
            manifest["metadata"]["price_usd"] = float(ledger_price)
            updated = True
            
        # Check and update product.price_usd
        prod_price = manifest.get("product", {}).get("price_usd")
        if prod_price is None or float(prod_price) != float(ledger_price):
            print(f"[{product_id}] Updating manifest product price: {prod_price} -> {ledger_price}")
            if "product" not in manifest: manifest["product"] = {}
            manifest["product"]["price_usd"] = float(ledger_price)
            updated = True

        if updated:
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)
            return True
        return False
    except Exception as e:
        print(f"[{product_id}] Error updating manifest: {e}")
        return False

def regenerate_promotions(product_id, price_float):
    """
    Forces regeneration of promotions by:
    1. Deleting existing blog markdown (to force regeneration)
    2. Calling build_channel_payloads
    3. Saving the results back to disk
    """
    promotions_dir = os.path.join(Config.OUTPUT_DIR, product_id, "promotions")
    if not os.path.exists(promotions_dir):
        os.makedirs(promotions_dir, exist_ok=True)
        
    # Delete existing markdown files to force regeneration
    for f_name in ["blog_longform.md", "blog_post.md", "medium_story.md"]:
        f_path = os.path.join(promotions_dir, f_name)
        if os.path.exists(f_path):
            try:
                os.remove(f_path)
                print(f"[{product_id}] Deleted old {f_name}")
            except Exception as e:
                print(f"[{product_id}] Failed to delete {f_name}: {e}")

    try:
        # Generate new payloads
        payloads = build_channel_payloads(product_id)
        
        # Save channel_payloads.json
        payloads_path = os.path.join(promotions_dir, "channel_payloads.json")
        with open(payloads_path, 'w', encoding='utf-8') as f:
            json.dump(payloads, f, indent=2, ensure_ascii=False)
            
        # Save generated blog markdown and HTML
        blog_data = payloads.get("blog", {})
        if blog_data.get("markdown"):
            with open(os.path.join(promotions_dir, "blog_post.md"), 'w', encoding='utf-8') as f:
                f.write(blog_data["markdown"])
        
        if blog_data.get("html"):
            with open(os.path.join(promotions_dir, "blog_post.html"), 'w', encoding='utf-8') as f:
                f.write(blog_data["html"])
                
        # Verify price in generated content
        content = blog_data.get("markdown", "") + blog_data.get("html", "")
        expected_str = f"${price_float:.2f}"
        if expected_str in content:
            print(f"[{product_id}] Verified price {expected_str} in generated content.")
            return True
        else:
            print(f"[{product_id}] WARNING: Price {expected_str} NOT found in generated content.")
            return False
            
    except Exception as e:
        print(f"[{product_id}] Error generating promotions: {e}")
        return False

def main():
    products = get_ledger_products()
    print(f"Found {len(products)} products in ledger.")
    
    count = 0
    for p in products:
        pid = p['id']
        price = p['price']
        
        if price is None:
            print(f"[{pid}] No price in ledger, skipping")
            continue
            
        try:
            price_float = float(price)
        except ValueError:
            print(f"[{pid}] Invalid price in ledger: {price}")
            continue

        # 1. Update manifest if needed
        manifest_updated = update_manifest(pid, price_float)
        
        # 2. Always regenerate to be safe, or at least check
        # For now, let's force regenerate for all to fix the $59 issue globally
        print(f"[{pid}] Regenerating promotions...")
        regenerate_promotions(pid, price_float)
            
        count += 1

if __name__ == "__main__":
    main()
