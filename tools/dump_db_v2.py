import sqlite3
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("Starting DB dump...", flush=True)
try:
    conn = sqlite3.connect('data/ledger.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT id, status, metadata_json FROM products LIMIT 3")
    rows = cur.fetchall()
    
    print(f"Found {len(rows)} rows.", flush=True)

    for row in rows:
        print(f"ID: {row['id']}", flush=True)
        print(f"Status: {row['status']}", flush=True)
        try:
            if row['metadata_json']:
                meta = json.loads(row['metadata_json'])
                url = meta.get('deployment_url')
                print(f"Deployment URL: {url}", flush=True)
            else:
                print("Metadata is empty/null", flush=True)
        except Exception as e:
            print(f"Metadata Error: {e}", flush=True)
        print("-" * 20, flush=True)

    conn.close()
except Exception as e:
    print(f"Fatal Error: {e}", flush=True)
