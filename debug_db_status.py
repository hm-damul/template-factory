import sqlite3
import os
import json

db_path = 'data/ledger.db'
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found.")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

try:
    print("--- Checking PROMOTED products ---")
    cursor.execute("SELECT id, topic, status, metadata_json FROM products WHERE status = 'PROMOTED' ORDER BY created_at DESC LIMIT 5")
    rows = cursor.fetchall()
    for row in rows:
        print(f"ID: {row['id']}")
        print(f"Topic: {row['topic']}")
        meta = json.loads(row['metadata_json']) if row['metadata_json'] else {}
        price = meta.get('price_usd')
        url = meta.get('deployment_url')
        print(f"Price: {price}")
        print(f"URL: {url}")
        print("-" * 20)

    print("\n--- Checking PUBLISHED products ---")
    cursor.execute("SELECT id, topic, status, metadata_json FROM products WHERE status = 'PUBLISHED' ORDER BY created_at DESC LIMIT 5")
    rows = cursor.fetchall()
    for row in rows:
        print(f"ID: {row['id']}")
        print(f"Topic: {row['topic']}")
        meta = json.loads(row['metadata_json']) if row['metadata_json'] else {}
        price = meta.get('price_usd')
        url = meta.get('deployment_url')
        print(f"Price: {price}")
        print(f"URL: {url}")
        print("-" * 20)

except Exception as e:
    print(f"Error querying DB: {e}")
finally:
    conn.close()
