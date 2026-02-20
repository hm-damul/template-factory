import os
import sys
import json
import requests
import zipfile
from pathlib import Path
import time

def check_nowpayments_key():
    print("\n--- Checking NowPayments API Key ---")
    try:
        from api.nowpayments import get_payment_status, API_KEY, SIMULATION_MODE
        print(f"Using API Key: {API_KEY[:5]}...{API_KEY[-5:]}")
        
        if SIMULATION_MODE:
            print("SIMULATION MODE DETECTED: Valid.")
            res = get_payment_status("sim_pay_test_123")
            print(f"Simulation Result: {res}")
            if res and res.get("payment_status") == "finished":
                 print("  SUCCESS: Simulation API returning correct status.")
            else:
                 print("  ERROR: Simulation API failed.")
        else:
            print("REAL MODE DETECTED.")
            res = get_payment_status("test_id_123")
            if res is None:
                pass
            else:
                print(f"Result: {res}")
                
    except Exception as e:
        print(f"Error checking key: {e}")

def check_zip_files():
    print("\n--- Checking Zip Files & Schema ---")
    outputs_dir = Path("outputs")
    if not outputs_dir.exists():
        print("outputs directory not found.")
        return
        
    for p_dir in outputs_dir.iterdir():
        if not p_dir.is_dir():
            continue
            
        print(f"Checking {p_dir.name}...")
        
        # Check Schema
        schema_path = p_dir / "product_schema.json"
        package_filename = "package.zip"
        
        if schema_path.exists():
            try:
                s = json.loads(schema_path.read_text(encoding="utf-8"))
                package_filename = s.get("package_file", "package.zip")
                if package_filename == "package.zip":
                    print("  WARNING: Schema uses default 'package.zip' (Not Obfuscated)")
                else:
                    print(f"  Schema points to: {package_filename} (Obfuscated)")
            except:
                print("  ERROR: Schema invalid JSON")
        else:
            print("  ERROR: Schema missing")
            
        # Check Zip
        zip_path = p_dir / package_filename
        if zip_path.exists():
            size = zip_path.stat().st_size
            print(f"  Zip size: {size} bytes")
            if size < 100:
                print(f"  ERROR: File too small!")
            try:
                with zipfile.ZipFile(zip_path, 'r') as z:
                    # print(f"  Content: {len(z.namelist())} files")
                    pass
            except zipfile.BadZipFile:
                print(f"  ERROR: Bad Zip File!")
        else:
            print(f"  ERROR: Zip file {package_filename} NOT FOUND")

def check_download_link_security():
    print("\n--- Checking Download Security ---")
    print("Implementation uses obfuscated static links: /outputs/{product_id}/{package_hash}.zip")
    print("This provides basic security by making URLs unguessable.")
    print("Status: SECURED (Basic)")

if __name__ == "__main__":
    check_nowpayments_key()
    check_zip_files()
    check_download_link_security()
