import os
import json
import random
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.product_generator import ProductGenerator, _render_landing_html_from_schema
try:
    from monetize_module import MonetizeModule, PaymentInjectConfig
except ImportError:
    # If not found in path, try adding current directory or project root explicitly
    sys.path.append(str(project_root))
    from monetize_module import MonetizeModule, PaymentInjectConfig

def update_prices_and_regenerate():
    products_dir = project_root / "outputs"
    if not products_dir.exists():
        print(f"Products directory not found: {products_dir}")
        return

    # generator = ProductGenerator() # Not needed if using functional approach
    price_options = [19.0, 29.0, 39.0, 49.0, 59.0, 69.0]
    updated_count = 0

    print("Starting price update and HTML regeneration...")

    for product_dir in products_dir.iterdir():
        if not product_dir.is_dir():
            continue

        manifest_path = product_dir / "manifest.json"
        if not manifest_path.exists():
            continue

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            meta = manifest.get("metadata", {})
            product_id = meta.get("product_id", product_dir.name)
            
            current_price = meta.get("price_usd")
            
            # Update price logic: if missing or fixed/default values, update it
            new_price = current_price
            should_update = False
            
            if not current_price:
                should_update = True
            else:
                try:
                    p_val = float(current_price)
                    if p_val in [19.9, 29.0, 49.0]: # Common defaults to change
                        should_update = True
                except:
                    should_update = True
            
            # Force update to ensure diversity if it looks like a default batch
            # Or just update everything to be safe if requested
            if should_update or True: # Force update for now to ensure diversity
                new_price = random.choice(price_options)
                meta["price_usd"] = new_price
                manifest["metadata"] = meta
                
                # Write manifest
                manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
                # print(f"Updated price for {product_id}: {current_price} -> {new_price}")

            # Now regenerate HTML with the new price
            schema_path = product_dir / "product_schema.json"
            if schema_path.exists():
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
            else:
                schema = {
                    "product_id": product_id,
                    "title": manifest.get("title", "Product"),
                    "sections": {}
                }
            
            # Inject new price
            price_str = f"${int(new_price)}"
            schema["_injected_price"] = price_str
            
            if "sections" not in schema: schema["sections"] = {}
            if "pricing" not in schema["sections"]: schema["sections"]["pricing"] = {}
            schema["sections"]["pricing"]["price"] = price_str
            
            # Save schema back (optional, but good for consistency)
            schema_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")

            # Generate HTML
            html = _render_landing_html_from_schema(schema)
            (product_dir / "index.html").write_text(html, encoding="utf-8")
            
            # Inject Payment Widget
            try:
                mm = MonetizeModule()
                # Use price from manifest/schema or random if not set (but we set it above)
                p_usd = float(meta.get("price_usd", 29.0))
                
                mm.inject_payment_logic(
                    target_html_path=str(product_dir / "index.html"),
                    config=PaymentInjectConfig(product_id=product_id, price_usd=p_usd)
                )
                # print(f"  -> Payment widget injected for {product_id}")
            except Exception as e:
                print(f"  -> Failed to inject payment widget: {e}")
            
            updated_count += 1
            print(f"[{updated_count}] Processed {product_id}: Price set to {price_str}")

        except Exception as e:
            print(f"Error processing {product_dir.name}: {e}")

    print(f"\nCompleted! Updated {updated_count} products.")

if __name__ == "__main__":
    update_prices_and_regenerate()
