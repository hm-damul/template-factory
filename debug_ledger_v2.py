import sqlite3
import os

db_path = 'd:/auto/MetaPassiveIncome_FINAL/data/ledger.db'
if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    # Try looking in root just in case
    db_path_root = 'd:/auto/MetaPassiveIncome_FINAL/ledger.db'
    if os.path.exists(db_path_root):
        print(f"Found at root instead: {db_path_root}")
        db_path = db_path_root
    else:
        exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print(f"Connected to {db_path}")

print("\n--- Product Status Counts ---")
try:
    cursor.execute('SELECT status, count(*) FROM products GROUP BY status')
    for row in cursor.fetchall():
        print(row)
except Exception as e:
    print(f"Error querying status counts: {e}")

print("\n--- Total Products ---")
try:
    cursor.execute('SELECT count(*) FROM products')
    print(f"Total: {cursor.fetchone()[0]}")
except Exception as e:
    print(f"Error counting products: {e}")

print("\n--- Sample Products (First 5) ---")
try:
    cursor.execute('SELECT id, status, metadata_json FROM products LIMIT 5')
    rows = cursor.fetchall()
    for row in rows:
        print(f"ID: {row[0]}, Status: {row[1]}")
        # print(f"Metadata: {row[2][:100]}...") # Truncate metadata
except Exception as e:
    print(f"Error fetching sample products: {e}")

conn.close()
