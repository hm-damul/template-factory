import sqlite3
import json
import requests
import sys

DB_PATH = "d:/auto/MetaPassiveIncome_FINAL/data/ledger.db"
PRODUCT_ID = "20260220-211248-digital-asset-bundle-2026-02-2"

def check_product():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM products WHERE id = ?", (PRODUCT_ID,))
    row = cur.fetchone()
    
    if not row:
        print(f"Product {PRODUCT_ID} not found in ledger.")
        return

    # Debug: print column names
    print(f"Columns: {row.keys()}")

    # Access by index if needed, or by name
    try:
        pid = row['id']
        status = row['status']
        # Use correct column name 'metadata_json'
        meta_json = row['metadata_json']
        print(f"Product ID: {pid}")
        print(f"Status: {status}")
        
        metadata = json.loads(meta_json) if meta_json else {}
        print("Metadata:")
        print(json.dumps(metadata, indent=2))
        
        deployment_url = metadata.get('deployment_url')
        print(f"Deployment URL: {deployment_url}")
    except Exception as e:
        print(f"Error accessing row data: {e}")
        # Fallback to index access if keys fail
        print(f"Raw Row: {tuple(row)}")

    # Check file existence
    import os
    index_path = f"outputs/{PRODUCT_ID}/index.html"
    if os.path.exists(index_path):
        print(f"\nFile exists: {index_path}")
    else:
        print(f"\nFile MISSING: {index_path}")
    
    # Check if local preview works
    try:
        print("\nChecking Local Preview (Port 8088)...")
        resp = requests.get(f"http://127.0.0.1:8088/preview/{PRODUCT_ID}", timeout=5)
        print(f"Local Preview Status: {resp.status_code}")
    except Exception as e:
        print(f"Local Preview Failed: {e}")

    # Check if dashboard checkout works
    try:
        print("\nChecking Dashboard Checkout (Port 8099)...")
        resp = requests.get(f"http://127.0.0.1:8099/checkout/{PRODUCT_ID}", timeout=5)
        print(f"Dashboard Checkout Status: {resp.status_code}")
    except Exception as e:
        print(f"Dashboard Checkout Failed: {e}")

    # Check Vercel URL
    vercel_url = f"https://metapassiveincome-final.vercel.app/outputs/{PRODUCT_ID}/index.html"
    try:
        print(f"\nChecking Vercel URL: {vercel_url}")
        resp = requests.head(vercel_url, timeout=5)
        print(f"Vercel URL Status: {resp.status_code}")
    except Exception as e:
        print(f"Vercel URL Failed: {e}")

    conn.close()

if __name__ == "__main__":
    check_product()
