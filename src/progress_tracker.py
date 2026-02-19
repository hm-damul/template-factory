import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PROGRESS_FILE = DATA_DIR / "progress.json"

def update_progress(
    task: str,
    status: str,
    progress: int = 0,
    details: Optional[str] = None,
    product_id: Optional[str] = None
) -> None:
    """
    Update the current progress of a long-running task.
    
    Args:
        task: Name of the task (e.g., "Product Creation", "Deployment")
        status: Current status/step description (e.g., "Generating Schema", "Uploading")
        progress: Integer 0-100 representing percentage
        details: Additional info (optional)
        product_id: ID of the product being worked on (optional)
    """
    data = {
        "task": task,
        "status": status,
        "progress": progress,
        "details": details or "",
        "product_id": product_id or "",
        "updated_at": time.time(),
        "updated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        # Use atomic write pattern
        temp_file = PROGRESS_FILE.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        temp_file.replace(PROGRESS_FILE)
    except Exception as e:
        print(f"Failed to update progress: {e}")

def get_progress() -> Dict[str, Any]:
    """Read the current progress."""
    if not PROGRESS_FILE.exists():
        return {
            "task": "Idle",
            "status": "Waiting for tasks",
            "progress": 0,
            "details": "",
            "updated_at": 0
        }
    
    try:
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
