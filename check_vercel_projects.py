
import sys
import os
import json
from pathlib import Path

PROJECT_ROOT = Path(r"d:\auto\MetaPassiveIncome_FINAL")
sys.path.append(str(PROJECT_ROOT))

from src.publisher import Publisher
from src.ledger_manager import LedgerManager

def check_projects():
    lm = LedgerManager()
    p = Publisher(lm)
    projects = p._get_all_projects()
    print(f"Current Vercel projects count: {len(projects)}")
    
    # Sort by creation date if available
    for i, proj in enumerate(projects[:5]):
        print(f"Project {i+1}: {proj.get('name')} (ID: {proj.get('id')})")

if __name__ == "__main__":
    check_projects()
