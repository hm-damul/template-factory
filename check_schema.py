
import sqlite3
import json

def check_schema():
    conn = sqlite3.connect('data/ledger.db')
    cur = conn.cursor()
    cur.execute('PRAGMA table_info(products)')
    schema = cur.fetchall()
    print("Schema:", schema)
    
    cur.execute('SELECT * FROM products LIMIT 1')
    row = cur.fetchone()
    if row:
        colnames = [desc[0] for desc in cur.description]
        print("Columns:", colnames)
    conn.close()

if __name__ == "__main__":
    check_schema()
