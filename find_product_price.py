
import sqlite3
import json

DB_PATH = "data/ledger.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("SELECT * FROM products WHERE topic LIKE ?", ('%TOP 20 B2B Ecommerce Examples%',))
rows = cursor.fetchall()

# Get column names
columns = [description[0] for description in cursor.description]

print(f"Found {len(rows)} products:")
for row in rows:
    row_dict = dict(zip(columns, row))
    print(json.dumps(row_dict, indent=2))

conn.close()
