
import sys
import os
sys.path.append(os.getcwd())
try:
    import topic_module
    print("Import success")
except Exception as e:
    print(f"Import failed: {e}")
