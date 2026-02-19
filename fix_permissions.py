import os
import shutil
from pathlib import Path

def fix_permissions():
    # 1. Create Vercel Config Directory
    vercel_dir = Path(r"C:\Users\us090\AppData\Roaming\com.vercel.cli\Data")
    try:
        vercel_dir.mkdir(parents=True, exist_ok=True)
        print(f"Created directory {vercel_dir}")
    except Exception as e:
        print(f"Failed to create {vercel_dir}: {e}")

    # 2. Check Startup Directory Writability
    startup_dir = Path(r"C:\Users\us090\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup")
    test_file = startup_dir / "test_write.txt"
    try:
        test_file.write_text("test")
        print(f"Startup folder is writable.")
        test_file.unlink()
    except Exception as e:
        print(f"Startup folder is NOT writable: {e}")

if __name__ == "__main__":
    fix_permissions()
