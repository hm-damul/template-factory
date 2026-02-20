import requests
import time
import subprocess
import sys
import os
import json
from pathlib import Path

# Configuration
API_URL = "http://localhost:5000"
PRODUCT_ID = "product_test_auto"
OUTPUTS_DIR = Path("outputs") / PRODUCT_ID
SCHEMA_PATH = OUTPUTS_DIR / "product_schema.json"
PACKAGE_ZIP = OUTPUTS_DIR / "secure_pkg_xyz.zip"

def setup_test_product():
    """Create a dummy product for testing"""
    if not OUTPUTS_DIR.exists():
        OUTPUTS_DIR.mkdir(parents=True)
    
    # Create schema with specific package name
    schema = {
        "product_id": PRODUCT_ID,
        "title": "Test Product",
        "package_file": "secure_pkg_xyz.zip",
        "sections": {
            "pricing": {"price": "19.99"}
        }
    }
    SCHEMA_PATH.write_text(json.dumps(schema), encoding="utf-8")
    
    # Create dummy package file
    PACKAGE_ZIP.write_text("dummy content", encoding="utf-8")
    print(f"[Setup] Created test product at {OUTPUTS_DIR}")

def start_server():
    """Start the API server in background"""
    # Set PYTHONPATH to include current directory so api.nowpayments works
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()
    env["SIMULATION_MODE"] = "true" # Force simulation mode
    
    # Run api/main.py
    process = subprocess.Popen(
        [sys.executable, "api/main.py"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    print("[Setup] Starting API server...")
    time.sleep(3) # Wait for server to start
    
    if process.poll() is not None:
        stdout, stderr = process.communicate()
        print(f"[Error] API Server failed to start with code {process.returncode}")
        print(f"[Error] Stdout: {stdout.decode()}")
        print(f"[Error] Stderr: {stderr.decode()}")
        sys.exit(1)
        
    print("[Setup] API server started (PID: {})".format(process.pid))
    return process

def test_flow():
    """Test the full payment flow"""
    print("\n[Test] Starting Payment Flow Test...")
    
    # 1. Start Payment
    start_url = f"{API_URL}/api/pay/start?product_id={PRODUCT_ID}&price_amount=19.99"
    try:
        resp = requests.get(start_url)
        data = resp.json()
        
        if resp.status_code != 200:
            print(f"[Fail] Start Payment failed: {data}")
            print(f"[Debug] Response headers: {resp.headers}")
            print(f"[Debug] Response URL: {resp.url}")
            return False
            
        print(f"[Pass] Payment Started. Invoice URL: {data['nowpayments'].get('invoice_url')}")
        payment_id = data['nowpayments']['payment_id'] # In simulation, this is our key
        
        # 2. Simulate Payment Completion (The check API in simulation mode might auto-confirm or we rely on mock status)
        # In our nowpayments.py simulation, get_payment_status returns 'finished' if ID starts with 'sim_'
        
        # 3. Check Status
        check_url = f"{API_URL}/api/pay/check?order_id={payment_id}&product_id={PRODUCT_ID}"
        for _ in range(3):
            resp = requests.get(check_url)
            data = resp.json()
            status = data.get('status')
            provider_status = data.get('provider_status')
            
            print(f"[Check] Status: {status}, Provider: {provider_status}")
            
            if status == 'paid':
                download_url = data.get('download_url')
                print(f"[Pass] Payment Confirmed! Download URL: {download_url}")
                
                # Verify Download URL matches schema
                expected_suffix = f"/outputs/{PRODUCT_ID}/secure_pkg_xyz.zip"
                if download_url.endswith(expected_suffix):
                    print("[Pass] Download URL matches obfuscated filename.")
                    return True
                else:
                    print(f"[Fail] Download URL mismatch. Expected endswith {expected_suffix}, got {download_url}")
                    return False
            
            time.sleep(1)
            
        print("[Fail] Payment did not complete in time.")
        return False

    except Exception as e:
        print(f"[Error] Test failed with exception: {e}")
        return False

def cleanup():
    """Clean up test files"""
    if SCHEMA_PATH.exists():
        os.remove(SCHEMA_PATH)
    if PACKAGE_ZIP.exists():
        os.remove(PACKAGE_ZIP)
    if OUTPUTS_DIR.exists():
        os.rmdir(OUTPUTS_DIR)
    print("[Cleanup] Test files removed.")

if __name__ == "__main__":
    setup_test_product()
    server_process = start_server()
    
    success = False
    try:
        success = test_flow()
    finally:
        server_process.terminate()
        server_process.wait()
        cleanup()
        
    if success:
        print("\nSUCCESS: System verification passed.")
        sys.exit(0)
    else:
        print("\nFAILURE: System verification failed.")
        sys.exit(1)
