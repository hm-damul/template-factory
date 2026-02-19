import sqlite3
import os

db_path = 'd:/auto/MetaPassiveIncome_FINAL/ledger.db'
if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("--- Product Status Counts ---")
try:
    cursor.execute('SELECT status, count(*) FROM products GROUP BY status')
    for row in cursor.fetchall():
        print(row)
except Exception as e:
    print(f"Error querying status counts: {e}")

print("\n--- Total Products ---")
cursor.execute('SELECT count(*) FROM products')
print(f"Total: {cursor.fetchone()[0]}")

print("\n--- Sample Products (First 5) ---")
cursor.execute('SELECT id, status, price, title FROM products LIMIT 5')
columns = [description[0] for description in cursor.description]
print(f"Columns: {columns}")
for row in cursor.fetchall():
    print(row)

conn.close()
