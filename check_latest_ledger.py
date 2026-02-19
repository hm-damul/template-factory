import sqlite3
import json
import os

DB_PATH = os.path.join("data", "ledger.db")

def check():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # id 컬럼 사용
    query = "SELECT id, status, metadata_json FROM products ORDER BY created_at DESC LIMIT 20"
    cursor.execute(query)
    rows = cursor.fetchall()
    
    print(f"{'PRODUCT_ID':<50} | {'STATUS':<20} | {'URL'}")
    print("-" * 120)
    for row in rows:
        pid, status, meta_json = row
        meta = json.loads(meta_json) if meta_json else {}
        url = meta.get('deployment_url', 'N/A')
        print(f"{pid:<50} | {status:<20} | {url}")
    
    conn.close()

if __name__ == "__main__":
    check()
