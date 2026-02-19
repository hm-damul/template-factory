import json
from pathlib import Path

p = Path("ledger.json")
if p.exists():
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
        counts = {}
        for item in data:
            s = item.get("status", "UNKNOWN")
            counts[s] = counts.get(s, 0) + 1
        print(f"Total Products: {len(data)}")
        print(f"Status Counts: {counts}")
    except Exception as e:
        print(f"Error reading ledger: {e}")
else:
    print("Ledger not found")
