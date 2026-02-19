import sqlite3
import json

def check_product():
    db_path = 'data/ledger.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, status, topic FROM products WHERE topic LIKE '%freelancer%' OR id LIKE '%freelancer%'")
    rows = cursor.fetchall()
    for row in rows:
        print(row)
    conn.close()

if __name__ == "__main__":
    check_product()
