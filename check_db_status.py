import sqlite3
import json

conn = sqlite3.connect('data/ledger.db')
cursor = conn.cursor()

cursor.execute("SELECT id, status, metadata_json FROM products WHERE metadata_json LIKE '%SaaS%' LIMIT 1")
row = cursor.fetchone()

if row:
    print("\nSample SaaS Product:")
    print(f"ID: {row[0]}")
    print(f"Status: {row[1]}")
    meta = json.loads(row[2])
    print(f"Price: {meta.get('price_usd')}")
    print(f"Final Price: {meta.get('final_price_usd')}")
    print(f"Title: {meta.get('title')}")

conn.close()

