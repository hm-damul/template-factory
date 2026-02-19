
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
    cursor.execute("SELECT id, topic, status, metadata_json, updated_at FROM products ORDER BY updated_at DESC LIMIT 10")
    rows = cursor.fetchall()
    
    print(f"{'ID':<40} | {'Status':<15} | {'Vercel URL'}")
    print("-" * 100)
    for row in rows:
        pid, topic, status, meta_json, updated_at = row
        meta = json.loads(meta_json) if meta_json else {}
        vercel_url = meta.get('vercel_url', 'N/A')
        print(f"{pid:<40} | {status:<15} | {vercel_url}")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
