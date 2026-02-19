
import os
import json
import random
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

from src.product_generator import _render_landing_html_from_schema, _validate_html, _sanitize_html
from src.utils import write_text, get_logger

logger = get_logger("update_prices")

def update_product_prices():
    outputs_dir = project_root / "outputs"
    if not outputs_dir.exists():
        logger.warning("No outputs directory found.")
        return

    updated_count = 0
    
    for product_dir in outputs_dir.iterdir():
        if not product_dir.is_dir():
            continue
            
        schema_path = product_dir / "product_schema.json"
        if not schema_path.exists():
            continue
            
        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                schema = json.load(f)
            
            # Check current price
            pricing = schema.get("sections", {}).get("pricing", {})
            current_price = pricing.get("price", "")
            
            # If price is generic or we want to randomize it to fix uniformity
            # Let's assign a random price from a set
            new_price_val = random.choice([19, 29, 39, 49, 59, 79])
            new_price = f"${new_price_val}"
            
            # Update schema
            if "sections" not in schema:
                schema["sections"] = {}
            if "pricing" not in schema["sections"]:
                schema["sections"]["pricing"] = {}
                
            schema["sections"]["pricing"]["price"] = new_price
            
            # Save schema
            with open(schema_path, "w", encoding="utf-8") as f:
                json.dump(schema, f, indent=2, ensure_ascii=False)
                
            # Regenerate index.html
            html = _render_landing_html_from_schema(schema)
            html = _sanitize_html(html)
            _validate_html(html)
            
            index_path = product_dir / "index.html"
            write_text(index_path, html)
            
            logger.info(f"Updated {product_dir.name}: {current_price} -> {new_price}")
            updated_count += 1
            
        except Exception as e:
            logger.error(f"Failed to update {product_dir.name}: {e}")

    logger.info(f"Total products updated: {updated_count}")

if __name__ == "__main__":
    update_product_prices()
