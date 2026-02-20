import sys
import json
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT))

try:
    from src.product_generator import _render_landing_html_from_schema
except ImportError:
    # If running from root, src is a package
    # But if imports inside src.product_generator are relative, they might fail if not run as module
    # Let's try to adjust sys.path to ensure src is found
    pass

def main():
    outputs_dir = PROJECT_ROOT / "outputs"
    if not outputs_dir.exists():
        print("Outputs directory not found.")
        return

    print(f"Scanning {outputs_dir}...")
    
    count = 0
    for product_dir in outputs_dir.iterdir():
        if not product_dir.is_dir():
            continue
            
        schema_path = product_dir / "product_schema.json"
        if not schema_path.exists():
            # print(f"Skipping {product_dir.name}: No schema found.")
            continue
            
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Error reading schema for {product_dir.name}: {e}")
            continue

        try:
            # Check if package_file is in schema
            pkg_file = schema.get("package_file")
            if not pkg_file:
                print(f"Warning: {product_dir.name} schema missing package_file. Defaulting to package.zip")
            
            # Regenerate HTML
            html = _render_landing_html_from_schema(schema, brand="MetaPassiveIncome")
            
            # Write back
            (product_dir / "index.html").write_text(html, encoding="utf-8")
            print(f"Regenerated index.html for {product_dir.name} (pkg: {pkg_file or 'default'})")
            count += 1
        except Exception as e:
            print(f"Error regenerating HTML for {product_dir.name}: {e}")
            import traceback
            traceback.print_exc()

    print(f"Completed. Regenerated {count} landing pages.")

if __name__ == "__main__":
    main()
