# -*- coding: utf-8 -*-
import subprocess
import sys
import os
import time
from pathlib import Path

def run_cmd(cmd):
    print(f"Executing: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.returncode

def main():
    # 1. Run auto_pilot to generate 1 product (batch=1)
    # We use --deploy 1 and --publish 1 as default for hands-off automation
    print("--- Starting Auto Pilot Batch ---")
    rc = run_cmd([
        sys.executable, "auto_pilot.py", 
        "--batch", "1"
    ])
    
    if rc != 0:
        print("Auto Pilot failed.")
        sys.exit(rc) # Exit with error code to notify GitHub Actions
    
    # 2. Run auto_heal just in case
    print("--- Running Auto Heal ---")
    run_cmd([sys.executable, "auto_heal_products.py"])
    
    print("--- Batch Completed ---")

if __name__ == "__main__":
    main()
