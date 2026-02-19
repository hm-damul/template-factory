
import sqlite3
import json
from pathlib import Path

DB_PATH = Path("data/ledger.db")

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT id, topic, metadata_json FROM products LIMIT 5")
    rows = cur.fetchall()
    
    for row in rows:
        try:
            meta = json.loads(row['metadata_json'])
            url = meta.get('deployment_url')
            print(f"ID: {row['id']}")
            print(f"  Topic: {row['topic']}")
            print(f"  URL: {url}")
        except Exception as e:
            print(f"Error parsing {row['id']}: {e}")

if __name__ == "__main__":
    main()
