import sqlite3
import os

db_path = 'data/ledger.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
try:
    cursor.execute("SELECT status FROM products WHERE status LIKE 'PROMOTED%' LIMIT 1")
    row = cursor.fetchone()
    if row:
        print(f"Status: '{row[0]}'")
    else:
        print("No PROMOTED items found.")
        
    cursor.execute("SELECT status FROM products WHERE status LIKE 'PUBLISHED%' LIMIT 1")
    row = cursor.fetchone()
    if row:
        print(f"Status: '{row[0]}'")

except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
