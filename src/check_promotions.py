
import sqlite3
import json
from pathlib import Path

# Fix path to db
project_root = Path(__file__).resolve().parents[1]
DB_PATH = project_root / "data" / "ledger.db"

def main():
    if not DB_PATH.exists():
        print(f"DB not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Check tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r['name'] for r in cur.fetchall()]
    print(f"Tables: {tables}")
    
    if 'promotions' in tables:
        print("\nPromotions table data:")
        cur.execute("SELECT * FROM promotions LIMIT 5")
        rows = cur.fetchall()
        for row in rows:
            print(dict(row))
            
    if 'products' in tables:
        print("\nProducts metadata check for WP:")
        cur.execute("SELECT id, metadata_json FROM products WHERE metadata_json LIKE '%wordpress%' LIMIT 5")
        rows = cur.fetchall()
        for row in rows:
            meta = json.loads(row['metadata_json'])
            print(f"ID: {row['id']}")
            print(f"WP Data: {meta.get('wordpress_url')}")

if __name__ == "__main__":
    main()
