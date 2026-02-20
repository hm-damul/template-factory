import os
import sys
import json
import shutil
import zipfile
import hashlib
from pathlib import Path

def calculate_hash(file_list):
    h = hashlib.md5()
    for f in sorted(file_list):
        h.update(str(f).encode('utf-8'))
        # optionally update with content, but filename hash is enough for obfuscation 
        # combined with random salt if needed. 
        # Better: just use random hex for security.
    return hashlib.sha256(os.urandom(32)).hexdigest()[:16]

def fix_zips():
    outputs_dir = Path("outputs")
    if not outputs_dir.exists():
        print("outputs directory not found.")
        return

    print("--- Fixing Zip Files & Obfuscating Names ---")
    
    for p_dir in outputs_dir.iterdir():
        if not p_dir.is_dir():
            continue
            
        product_id = p_dir.name
        print(f"Processing {product_id}...")
        
        # 1. Identify content to zip
        # We want to zip everything in p_dir EXCEPT existing zips
        files_to_zip = []
        for root, dirs, files in os.walk(p_dir):
            for file in files:
                if file.endswith(".zip"):
                    continue
                file_path = Path(root) / file
                files_to_zip.append(file_path)
        
        if not files_to_zip:
            print(f"  WARNING: No content files found for {product_id}. Skipping.")
            continue
            
        # 2. Generate new zip name
        # Check if schema already has a name
        schema_path = p_dir / "product_schema.json"
        existing_package_name = "package.zip"
        
        if schema_path.exists():
            try:
                with open(schema_path, 'r', encoding='utf-8') as f:
                    schema = json.load(f)
                    existing_package_name = schema.get("package_file", "package.zip")
            except:
                pass

        # If existing name is package.zip, we want to change it.
        # If it's already obfuscated, we can keep it or regenerate.
        # Let's regenerate to ensure validity.
        
        random_hash = hashlib.sha256(os.urandom(32)).hexdigest()[:12]
        new_zip_name = f"package_{random_hash}.zip"
        new_zip_path = p_dir / new_zip_name
        
        # 3. Create Zip
        print(f"  Creating {new_zip_name} with {len(files_to_zip)} files...")
        try:
            with zipfile.ZipFile(new_zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
                for file_path in files_to_zip:
                    arcname = file_path.relative_to(p_dir)
                    z.write(file_path, arcname)
        except Exception as e:
            print(f"  ERROR creating zip: {e}")
            continue
            
        # 4. Update Schema
        if schema_path.exists():
            try:
                with open(schema_path, 'r', encoding='utf-8') as f:
                    schema = json.load(f)
                
                schema["package_file"] = new_zip_name
                
                with open(schema_path, 'w', encoding='utf-8') as f:
                    json.dump(schema, f, indent=2)
                print("  Updated product_schema.json")
            except Exception as e:
                print(f"  ERROR updating schema: {e}")
        
        # 5. Clean up old zips
        for file in p_dir.glob("package*.zip"):
            if file.name != new_zip_name:
                try:
                    os.remove(file)
                    print(f"  Removed old zip: {file.name}")
                except Exception as e:
                    print(f"  Failed to remove {file.name}: {e}")

if __name__ == "__main__":
    fix_zips()
