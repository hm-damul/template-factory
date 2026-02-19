import sqlite3
import json

conn = sqlite3.connect('data/ledger.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("Fetching products...")
cur.execute("SELECT id, status, metadata FROM products LIMIT 3")
rows = cur.fetchall()

for row in rows:
    print(f"ID: {row['id']}")
    print(f"Status: {row['status']}")
    try:
        meta = json.loads(row['metadata'])
        print(f"Deployment URL: {meta.get('deployment_url')}")
        print(f"Meta Keys: {list(meta.keys())}")
    except Exception as e:
        print(f"Metadata Error: {e}")
        print(f"Raw Metadata: {row['metadata'][:100]}...")
    print("-" * 20)

conn.close()
