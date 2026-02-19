# -*- coding: utf-8 -*-
import re
import time
from pathlib import Path

def get_vercel_reset_info():
    log_file = Path("logs/product_factory.log")
    if not log_file.exists():
        print("Log file not found.")
        return

    content = log_file.read_text(encoding="utf-8", errors="ignore")
    # Search for Vercel 402 error messages with retry time
    # Example: "try again in 23 h" or "try again in 14 m"
    pattern = r"try again in (\d+)\s*(h|m)"
    matches = list(re.finditer(pattern, content))
    
    if not matches:
        print("No Vercel limit messages found in logs.")
        return

    # Get the last match
    last_match = matches[-1]
    value = int(last_match.group(1))
    unit = last_match.group(2)
    
    # Estimate reset time based on log file modification time or current time
    # For safety, use current time as the reference
    current_time = time.time()
    
    if unit == 'h':
        remaining_seconds = value * 3600
    else:
        remaining_seconds = value * 60
        
    reset_time_s = current_time + remaining_seconds
    
    print(f"Latest Vercel Limit Detected: {last_match.group(0)}")
    print(f"Estimated Reset Time (Local): {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(reset_time_s))}")
    
    wait_hours = remaining_seconds / 3600
    print(f"Remaining wait time: {wait_hours:.2f} hours")

if __name__ == "__main__":
    get_vercel_reset_info()
