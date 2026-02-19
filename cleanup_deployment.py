import os
import shutil
from pathlib import Path

def cleanup():
    # 1. Cleanup Vercel Config Directory
    vercel_dir = Path(r"C:\Users\us090\AppData\Roaming\com.vercel.cli")
    if vercel_dir.exists():
        try:
            shutil.rmtree(vercel_dir)
            print(f"Deleted directory {vercel_dir}")
        except Exception as e:
            print(f"Failed to delete {vercel_dir}: {e}")
    else:
        print(f"{vercel_dir} not found")

    # 2. Cleanup Startup Shortcut
    shortcut = Path(r"C:\Users\us090\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\MetaPassiveIncome_Auto.lnk")
    if shortcut.exists():
        try:
            shortcut.unlink()
            print(f"Deleted {shortcut}")
        except Exception as e:
            print(f"Failed to delete {shortcut}: {e}")
    else:
        print(f"{shortcut} not found")

if __name__ == "__main__":
    cleanup()
