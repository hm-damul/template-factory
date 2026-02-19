
import sqlite3
import json

def check_new_product():
    conn = sqlite3.connect('data/ledger.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('SELECT id, status, metadata_json FROM products WHERE id = ?', ('20260215-063000-freelancer-consultant-landing-',))
    row = cur.fetchone()
    if row:
        print(json.dumps(dict(row), ensure_ascii=False, indent=2))
    conn.close()

if __name__ == "__main__":
    check_new_product()
