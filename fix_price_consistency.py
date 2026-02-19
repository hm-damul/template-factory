
import sqlite3
import json
import os
from pathlib import Path
import re

DB_PATH = Path("data/ledger.db")
OUTPUTS_DIR = Path("outputs")

def fix_all():
    print("Starting comprehensive fix...")
    
    # 1. Update Database
    if DB_PATH.exists():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Update price in metadata_json to 59
        # We use json_set to update specific fields
        try:
            print("Updating database prices...")
            
            # Ensure metadata_json is not NULL
            cursor.execute("UPDATE products SET metadata_json = '{}' WHERE metadata_json IS NULL")
            
            cursor.execute("""
                UPDATE products 
                SET metadata_json = json_set(metadata_json, '$.price_usd', 59)
            """)
            cursor.execute("""
                UPDATE products 
                SET metadata_json = json_set(metadata_json, '$.price', 59)
            """)
            cursor.execute("""
                UPDATE products 
                SET metadata_json = json_set(metadata_json, '$.price_numeric', 59)
            """)
            cursor.execute("""
                UPDATE products 
                SET metadata_json = json_set(metadata_json, '$.price_display', '$59')
            """)
            
            # Ensure status is PROMOTED for everything that looks ready
            # Or at least fix the 'Pending' ones if they have content
            # The user said 102 are published, so we trust the current status mostly, 
            # but we ensure consistency.
            # Let's not blindly change status unless it's clearly wrong, 
            # but we WILL ensure price is 59.
            
            conn.commit()
            print("Database updated.")
        except Exception as e:
            print(f"DB Update Error: {e}")
        finally:
            conn.close()

    # 2. Update File System (outputs)
    if OUTPUTS_DIR.exists():
        print("Scanning outputs directory...")
        count = 0
        for item in OUTPUTS_DIR.iterdir():
            if item.is_dir():
                process_product_dir(item)
                count += 1
        print(f"Processed {count} product directories.")

def process_product_dir(p_dir: Path):
    # 2.1 Update product_schema.json (Critical for Payment API)
    schema_path = p_dir / "product_schema.json"
    if schema_path.exists():
        try:
            content = schema_path.read_text(encoding="utf-8")
            data = json.loads(content)
            
            changed = False
            # Fix injected price
            if data.get("_injected_price") != "$59.00":
                data["_injected_price"] = "$59.00"
                changed = True
            
            # Fix sections.pricing.price
            if "sections" in data and "pricing" in data["sections"]:
                if data["sections"]["pricing"].get("price") != "$59.00":
                    data["sections"]["pricing"]["price"] = "$59.00"
                    changed = True
            
            if changed:
                schema_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                # print(f"Updated schema for {p_dir.name}")
        except Exception as e:
            print(f"Error updating schema {p_dir.name}: {e}")

    # 2.2 Update manifest.json
    manifest_path = p_dir / "manifest.json"
    if manifest_path.exists():
        try:
            content = manifest_path.read_text(encoding="utf-8")
            data = json.loads(content)
            
            changed = False
            if data.get("price_usd") != 59:
                data["price_usd"] = 59
                changed = True
            if data.get("price") != 59:
                data["price"] = 59
                changed = True
                
            if changed:
                manifest_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            print(f"Error updating manifest {p_dir.name}: {e}")

    # 2.3 Update index.html (Landing Page)
    index_path = p_dir / "index.html"
    if index_path.exists():
        update_file_content(index_path, ["$179", "179.00", "$49", "49.00", "$29", "29.00"], ["$59", "59.00", "$59", "59.00", "$59", "59.00"])

    # 2.4 Update Promotional Content
    promos_dir = p_dir / "promotions"
    if promos_dir.exists():
        for f in promos_dir.iterdir():
            if f.suffix in ['.html', '.md', '.txt', '.json']:
                update_file_content(f, ["$179", "179.00", "$49", "49.00", "$29", "29.00"], ["$59", "59.00", "$59", "59.00", "$59", "59.00"])

def update_file_content(file_path: Path, targets: list, replacements: list):
    try:
        content = file_path.read_text(encoding="utf-8")
        original_content = content
        
        # Simple string replacement for now, can be regex if needed
        # We map target[i] -> replacement[i]
        # Actually, we just want to unify everything to 59.
        # So we replace known wrong prices with $59 or 59.00
        
        # Handle $179 -> $59
        content = content.replace("$179", "$59")
        content = content.replace("179.00", "59.00")
        content = content.replace("$179.00", "$59.00")
        
        # Handle $49 -> $59
        content = content.replace("$49", "$59")
        content = content.replace("49.00", "59.00")
        
        # Handle $29 -> $59
        content = content.replace("$29", "$59")
        content = content.replace("29.00", "59.00")
        
        # Handle $39 -> $59
        content = content.replace("$39", "$59")
        content = content.replace("39.00", "59.00")

        # Handle 0.0716 ETH (approx $179) -> 0.0236 ETH (approx $59)
        # $59 / 2500 = 0.0236
        content = content.replace("0.0716", "0.0236")
        
        if content != original_content:
            file_path.write_text(content, encoding="utf-8")
            # print(f"Updated {file_path.name}")
            
    except Exception as e:
        print(f"Error updating file {file_path}: {e}")

if __name__ == "__main__":
    fix_all()
