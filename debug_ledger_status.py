import sqlite3
import os

db_path = 'data/ledger.db'
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found.")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
try:
    cursor.execute("SELECT status, COUNT(*) FROM products GROUP BY status")
    results = cursor.fetchall()
    print(f"Stats for {db_path}:")
    for status, count in results:
        print(f"{status}: {count}")
    
    # Calculate totals
    total = sum(c for s, c in results)
    published = sum(c for s, c in results if s in ["PUBLISHED", "PROMOTED"])
    
    print("-" * 20)
    print(f"Total: {total}")
    print(f"Published: {published}")
        
except Exception as e:
    print(f"Error querying DB: {e}")
finally:
    conn.close()
