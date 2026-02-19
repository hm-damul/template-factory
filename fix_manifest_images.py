# -*- coding: utf-8 -*-
import json
from pathlib import Path
import sys
import product_factory

def fix_manifests():
    root = Path(__file__).parent
    outputs_dir = root / "outputs"
    
    if not outputs_dir.exists():
        print("outputs dir not found")
        return

    for product_dir in outputs_dir.iterdir():
        if not product_dir.is_dir():
            continue
            
        manifest_path = product_dir / "manifest.json"
        if not manifest_path.exists():
            continue
            
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Error reading {manifest_path}: {e}")
            continue
            
        screenshot_url = data.get("screenshot_url")
        topic = data.get("topic", "Digital Product")
        product_id = data.get("product_id", product_dir.name)
        
        if not screenshot_url:
            print(f"Fixing missing screenshot for {product_id}...")
            
            # Generate assets using the updated product_factory logic
            assets_dir = product_dir / "assets"
            new_screenshot_url = product_factory.write_assets(assets_dir, product_id, topic)
            
            if new_screenshot_url:
                data["screenshot_url"] = new_screenshot_url
                
                # Update manifest.json
                # Use _atomic_write_json logic from product_factory if available, or just write
                manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"Updated manifest for {product_id}")
            else:
                print(f"Failed to generate screenshot for {product_id}")
        else:
            print(f"Screenshot already exists for {product_id}: {screenshot_url}")

if __name__ == "__main__":
    fix_manifests()
