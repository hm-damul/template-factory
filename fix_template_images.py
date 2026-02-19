import json
import os
import hashlib
import sys

# src 디렉토리를 path에 추가하여 임포트 가능하게 함
sys.path.append(os.getcwd())

from src.product_generator import _render_landing_html_from_schema

def calculate_checksum(file_path):
    with open(file_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def fix_product(product_id):
    product_dir = f"outputs/{product_id}"
    schema_path = os.path.join(product_dir, "product_schema.json")
    index_path = os.path.join(product_dir, "index.html")
    manifest_path = os.path.join(product_dir, "manifest.json")

    if not os.path.exists(schema_path):
        print(f"Schema not found for {product_id}")
        return

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    # Regenerate HTML (내부적으로 개선된 이미지 풀과 로직 사용)
    new_html = _render_landing_html_from_schema(schema)
    
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(new_html)
    
    print(f"Regenerated index.html for {product_id}")

    # Update manifest checksum
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        
        if "checksums" not in manifest:
            manifest["checksums"] = {}
            
        manifest["checksums"]["index.html"] = calculate_checksum(index_path)
        
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        print(f"Updated manifest.json for {product_id}")

if __name__ == "__main__":
    products = [
        "20260214-140141-ai-dev-income",
        "20260214-133737-ai-powered-passive-income-syst",
        "20260214-130903-ai-trading-bot"
    ]
    for pid in products:
        fix_product(pid)
