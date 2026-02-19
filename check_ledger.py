import sqlite3
from pathlib import Path

def check_ledger():
    db_path = Path('data/ledger.db')
    if not db_path.exists():
        print("Ledger DB not found at data/ledger.db")
        return
        
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    print("--- Product Status Summary ---")
    cur.execute("SELECT status, COUNT(*) FROM products GROUP BY status")
    for row in cur.fetchall():
        print(f"{row[0]}: {row[1]}")
        
    print("\n--- Latest 5 Products ---")
    cur.execute("SELECT id, topic, status, created_at, metadata_json FROM products ORDER BY created_at DESC LIMIT 5")
    for row in cur.fetchall():
        print(f"ID: {row[0]}, Topic: {row[1]}, Status: {row[2]}, Created: {row[3]}", flush=True)
        # Extract price from metadata
        import json
        try:
            if row[4]:
                meta = json.loads(row[4])
                print(f"  Price: {meta.get('price_numeric')} / {meta.get('price_display')}", flush=True)
            else:
                print("  Price: No Metadata", flush=True)
        except Exception as e:
            print(f"  Price: Error {e}", flush=True)
        
    conn.close()

if __name__ == "__main__":
    check_ledger()
