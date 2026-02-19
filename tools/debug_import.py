import sys
import os
from pathlib import Path

# Add project root to sys.path
root = str(Path(os.getcwd()).resolve())
if root not in sys.path:
    sys.path.insert(0, root)

print(f"Root: {root}")
print(f"Sys.path: {sys.path}")

try:
    print("Importing api.main...")
    import api.main
    print("Success importing api.main")
except Exception as e:
    print(f"Failed to import api.main: {e}")
    import traceback
    traceback.print_exc()

try:
    print("Importing payment_api...")
    import payment_api
    print("Success importing payment_api")
except Exception as e:
    print(f"Failed to import payment_api: {e}")
    import traceback
    traceback.print_exc()
