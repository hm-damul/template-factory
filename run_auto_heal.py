
import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent))

from src.auto_heal_system import AutoHealSystem

if __name__ == "__main__":
    print("Running Auto Heal System...")
    healer = AutoHealSystem()
    healer.run_full_audit_and_heal()
    print("Auto Heal System completed.")
