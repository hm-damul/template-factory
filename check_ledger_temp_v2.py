
import sqlite3
import json
import os

db_path = 'data/ledger.db'
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("SELECT id, status, metadata_json FROM products WHERE status='PUBLISHED' ORDER BY updated_at DESC LIMIT 10")
    rows = cursor.fetchall()
    
    print(f"{'ID':<50} | {'Status':<10} | {'Deployment URL'}")
    print("-" * 120)
    for row in rows:
        pid, status, meta_json = row
        meta = json.loads(meta_json) if meta_json else {}
        # Try both common keys
        url = meta.get('deployment_url') or meta.get('vercel_url') or 'N/A'
        print(f"{pid:<50} | {status:<10} | {url}")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
