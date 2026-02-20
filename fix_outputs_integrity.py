import os
import json
import secrets
import shutil
from pathlib import Path

OUTPUTS_DIR = Path("outputs")

def generate_obfuscated_name():
    return f"package_{secrets.token_hex(6)}.zip"

def ensure_schema(folder, product_id, zip_name):
    schema_path = folder / "product_schema.json"
    schema = {}
    
    if schema_path.exists():
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except:
            print(f"  [!] Invalid schema in {folder}, recreating...")
    
    # Update or create fields
    if "product_id" not in schema:
        schema["product_id"] = product_id
    
    schema["package_file"] = zip_name
    
    # Ensure basic structure if empty
    if "title" not in schema:
        # Try to read from product.md
        md_path = folder / "product.md"
        if md_path.exists():
            content = md_path.read_text(encoding="utf-8").splitlines()
            if content and content[0].startswith("# "):
                schema["title"] = content[0][2:].strip()
        
        if "title" not in schema:
            schema["title"] = product_id.replace("-", " ").title()

    schema_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  [+] Updated schema for {product_id} -> {zip_name}")

def fix_folder(folder):
    if not folder.is_dir():
        return

    product_id = folder.name
    print(f"Checking {product_id}...")

    # Find zip files
    zips = list(folder.glob("*.zip"))
    current_zip = None
    
    # Priority: package_*.zip (already obfuscated) > package.zip > bonus_en.zip > *.zip
    obfuscated = [z for z in zips if z.name.startswith("package_") and len(z.name) > 15]
    if obfuscated:
        current_zip = obfuscated[0]
    elif (folder / "package.zip").exists():
        current_zip = folder / "package.zip"
    elif (folder / "bonus_en.zip").exists():
        current_zip = folder / "bonus_en.zip"
    elif zips:
        current_zip = zips[0]
    
    # If no zip, create dummy if it's a valid product folder (has html or md)
    if not current_zip:
        if (folder / "index.html").exists() or (folder / "product.md").exists():
            print("  [!] No zip found. Creating dummy package.")
            dummy_zip = folder / "package.zip"
            # Create a valid empty zip
            shutil.make_archive(str(folder / "package"), 'zip', root_dir=folder, base_dir=".", dry_run=False)
            # shutil.make_archive adds .zip extension
            if (folder / "package.zip").exists():
                 current_zip = folder / "package.zip"
    
    if not current_zip:
        print("  [-] Skipped (no content)")
        return

    # Rename if necessary (obfuscate)
    final_name = current_zip.name
    if current_zip.name == "package.zip" or current_zip.name == "bonus_en.zip" or len(current_zip.name) < 15:
        new_name = generate_obfuscated_name()
        current_zip.rename(folder / new_name)
        final_name = new_name
        print(f"  [+] Renamed {current_zip.name} to {final_name}")
    
    # Ensure schema points to this file
    ensure_schema(folder, product_id, final_name)

def main():
    if not OUTPUTS_DIR.exists():
        print("outputs/ directory not found.")
        return

    for folder in OUTPUTS_DIR.iterdir():
        fix_folder(folder)

if __name__ == "__main__":
    main()
