
import sqlite3
import json

db_path = "data/ledger.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT id, topic, status, created_at FROM products ORDER BY created_at DESC LIMIT 10")
rows = cursor.fetchall()

print("Latest 10 products:")
for row in rows:
    print(f"ID: {row[0]}, Topic: {row[1]}, Status: {row[2]}, Created At: {row[3]}")

conn.close()
