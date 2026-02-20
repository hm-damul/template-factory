import os
import json
import sqlite3
import glob
from pathlib import Path
from src.config import Config

# Initialize
project_root = Path("d:/auto/MetaPassiveIncome_FINAL")
outputs_dir = project_root / "outputs"
db_path = project_root / "data" / "ledger.db"

def fix_product(product_dir):
    product_id = product_dir.name
    schema_path = product_dir / "product_schema.json"
    index_path = product_dir / "index.html"
    manifest_path = product_dir / "manifest.json"
    
    if not schema_path.exists():
        print(f"[{product_id}] No schema found, skipping.")
        return

    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
    except Exception as e:
        print(f"[{product_id}] Error reading schema: {e}")
        return

    # Determine correct price from schema
    # Logic: sections.pricing.price > schema.org price > 29.00 default
    correct_price = 29.00
    
    # Try sections.pricing.price
    try:
        p_str = schema.get("sections", {}).get("pricing", {}).get("price", "")
        if p_str:
            correct_price = float(p_str.replace("$", "").replace(",", ""))
    except:
        pass
        
    print(f"[{product_id}] Correct Price from Schema: {correct_price}")

    # 1. Fix index.html
    if index_path.exists():
        try:
            content = index_path.read_text(encoding="utf-8")
            # Look for common incorrect prices like 49.00, 59.00, 97.00
            # Only replace if they differ from correct_price
            
            updated = False
            for bad_price in [49.00, 59.00, 97.00, 39.00, 19.00]:
                if bad_price == correct_price: continue
                
                bad_str = f"{bad_price:.2f}"
                correct_str = f"{correct_price:.2f}"
                
                if bad_str in content:
                    # Contextual check: ensure it's a price display, not some random number
                    # But for now, simple replacement is safer than regex complexity if we target specific strings like "$49.00"
                    
                    # Replace "$49.00" -> "$29.00"
                    if f"${bad_str}" in content:
                        content = content.replace(f"${bad_str}", f"${correct_str}")
                        updated = True
                        print(f"[{product_id}] Fixed index.html: ${bad_str} -> ${correct_str}")
                    
                    # Replace "49.00" (raw) - risky?
                    # Let's stick to strict patterns if possible.
                    # The landing page has "$49.00/mo" -> replace "$49.00"
                    
                    # Also replace in JSON-LD if present and wrong
                    # "price": "49.00"
                    if f'"price": "{bad_str}"' in content:
                        content = content.replace(f'"price": "{bad_str}"', f'"price": "{correct_str}"')
                        updated = True
            
            if updated:
                index_path.write_text(content, encoding="utf-8")
        except Exception as e:
            print(f"[{product_id}] Error fixing index.html: {e}")

    # 2. Fix manifest.json
    if manifest_path.exists():
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            
            updated = False
            
            # Metadata
            if "metadata" not in manifest: manifest["metadata"] = {}
            curr_meta = manifest["metadata"].get("price_usd")
            if curr_meta is None or float(curr_meta) != correct_price:
                manifest["metadata"]["price_usd"] = correct_price
                updated = True
                print(f"[{product_id}] Fixed manifest metadata: {curr_meta} -> {correct_price}")
                
            # Product
            if "product" not in manifest: manifest["product"] = {}
            curr_prod = manifest["product"].get("price_usd")
            if curr_prod is None or float(curr_prod) != correct_price:
                manifest["product"]["price_usd"] = correct_price
                updated = True
                print(f"[{product_id}] Fixed manifest product: {curr_prod} -> {correct_price}")
                
            if updated:
                with open(manifest_path, 'w', encoding='utf-8') as f:
                    json.dump(manifest, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[{product_id}] Error fixing manifest: {e}")

    # 3. Fix Ledger DB
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get current metadata
        cursor.execute("SELECT metadata_json FROM products WHERE id=?", (product_id,))
        row = cursor.fetchone()
        if row:
            meta = json.loads(row[0]) if row[0] else {}
            curr_db_price = meta.get("price_usd")
            
            if curr_db_price is None or float(curr_db_price) != correct_price:
                meta["price_usd"] = correct_price
                meta["final_price_usd"] = correct_price
                
                new_meta_json = json.dumps(meta)
                cursor.execute("UPDATE products SET metadata_json=? WHERE id=?", (new_meta_json, product_id))
                conn.commit()
                print(f"[{product_id}] Fixed DB: {curr_db_price} -> {correct_price}")
        
        conn.close()
    except Exception as e:
        print(f"[{product_id}] Error fixing DB: {e}")

def main():
    print("Starting pricing mismatch fix...")
    
    # Process all directories in outputs
    for product_dir in outputs_dir.iterdir():
        if product_dir.is_dir() and (product_dir / "product_schema.json").exists():
            fix_product(product_dir)
            
    print("Pricing mismatch fix completed.")

if __name__ == "__main__":
    main()
