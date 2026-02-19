
import sqlite3
import os

db_path = "data/ledger.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id = '20260213-154551------' OR topic LIKE '%프리랜서%';")
    print(f"Deleted {cursor.rowcount} entries.")
    conn.commit()
    conn.close()
else:
    print("DB not found.")
