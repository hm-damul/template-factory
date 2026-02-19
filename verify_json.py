import sys
import os

print(f"Python executable: {sys.executable}")
print(f"CWD: {os.getcwd()}")
print(f"sys.path: {sys.path}")

try:
    import json
    print(f"json module: {json}")
    print(f"json file: {json.__file__}")
except ImportError as e:
    print(f"Error importing json: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")

try:
    from src.product_schema import get_product_schema_definition
    print("src.product_schema imported successfully")
except ImportError as e:
    print(f"Error importing src.product_schema: {e}")
except Exception as e:
    print(f"Unexpected error importing src.product_schema: {e}")
