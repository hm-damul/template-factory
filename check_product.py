import sqlite3
import json

db_path = "d:/auto/MetaPassiveIncome_FINAL/data/ledger.db"
pid = "20260219-131418-20-profitable-saas-micro-saas"

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
cursor.execute("SELECT * FROM products WHERE id=?", (pid,))
row = cursor.fetchone()

if row:
    print(f"ID: {row['id']}")
    print(f"Status: {row['status']}")
    print(f"Metadata: {row['metadata_json']}")
else:
    print("Not found")
conn.close()