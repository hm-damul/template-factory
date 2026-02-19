# -*- coding: utf-8 -*-
import os
import re

log_path = r"d:/auto/MetaPassiveIncome_FINAL/logs/product_factory.log"

if os.path.exists(log_path):
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
        
    # Pattern to find PIPELINE_FAILED updates and associated error info
    # Example: update_product_status(product_id, "PIPELINE_FAILED", metadata={"error": e.message, "stage": e.stage, ...})
    # But let's look for the ProductionError log right before it
    # 2026-02-13 11:16:29,222 - src.utils - ERROR - [ProductionError] Stage: ..., Message: ...
    
    error_pattern = r"\[ProductionError\] Stage: (.*?), Product ID: (.*?), Message: (.*?), Original: (.*)"
    matches = re.findall(error_pattern, content)
    
    print(f"Found {len(matches)} detailed ProductionError entries.")
    
    # Count stages
    stages = {}
    for stage, pid, msg, orig in matches:
        stages[stage] = stages.get(stage, 0) + 1
        
    print("\nFailures by Stage:")
    for stage, count in sorted(stages.items(), key=lambda x: x[1], reverse=True):
        print(f" - {stage}: {count}")
        
    print("\nLast 10 Failure Messages:")
    for stage, pid, msg, orig in matches[-10:]:
        print(f" - [{stage}] {msg[:100]}...")
else:
    print("Log file not found.")
