
import os
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.absolute()
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

def fix_missing_schemas():
    print("--- Fixing Missing Schemas ---")
    if not OUTPUTS_DIR.exists():
        print("outputs directory not found.")
        return

    count = 0
    for p_dir in OUTPUTS_DIR.iterdir():
        if not p_dir.is_dir():
            continue
            
        schema_path = p_dir / "product_schema.json"
        if schema_path.exists():
            continue
            
        print(f"Missing schema for {p_dir.name}. Attempting to generate...")
        
        # Try to find price in index.html
        index_path = p_dir / "index.html"
        price = "49.00"
        title = "Digital Product"
        
        if index_path.exists():
            try:
                with open(index_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Regex for JSON-LD price
                price_match = re.search(r'"price":\s*"(\d+\.?\d*)"', content)
                if price_match:
                    price = price_match.group(1)
                    print(f"  Found price in index.html: {price}")
                else:
                    # Regex for displayed price like $49
                    display_match = re.search(r'\$(\d+\.?\d*)', content)
                    if display_match:
                        price = display_match.group(1)
                        print(f"  Found price in display: {price}")
                        
                # Regex for title
                title_match = re.search(r'<title>(.*?)</title>', content)
                if title_match:
                    title = title_match.group(1).split('|')[0].strip()
                    
            except Exception as e:
                print(f"  Error reading index.html: {e}")
        
        # Create minimal schema
        schema = {
            "product_id": p_dir.name,
            "title": title,
            "sections": {
                "pricing": {
                    "price": f"${price}"
                }
            },
            "price": price
        }
        
        try:
            with open(schema_path, 'w', encoding='utf-8') as f:
                json.dump(schema, f, indent=2)
            print(f"  Created product_schema.json for {p_dir.name}")
            count += 1
        except Exception as e:
            print(f"  Error creating schema: {e}")

    print(f"--- Fixed {count} missing schemas ---")

if __name__ == "__main__":
    fix_missing_schemas()
