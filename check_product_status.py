
import sqlite3
import json

def check_products():
    conn = sqlite3.connect('data/ledger.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    ids = ('20260215-000641-freelancer-consultant-landing-', '20260213-154551-프리랜서-컨설턴트-서비스-소개-랜딩-페이지')
    cur.execute('SELECT id, status FROM products WHERE id IN (?, ?)', ids)
    rows = cur.fetchall()
    for row in rows:
        print(dict(row))
    conn.close()

if __name__ == "__main__":
    check_products()
