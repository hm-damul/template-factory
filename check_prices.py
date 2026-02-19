
import sqlite3
import json
from pathlib import Path

def main():
    db_path = Path("data/ledger.db")
    if not db_path.exists():
        print("ledger.db not found!")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Check total count
    cur.execute("SELECT count(*) FROM products")
    total = cur.fetchone()[0]
    print(f"Total Products in DB: {total}")
    
    # Check Status Distribution
    cur.execute("SELECT status, count(*) FROM products GROUP BY status")
    print("\n--- Status Distribution ---")
    for row in cur.fetchall():
        print(f"{row[0]}: {row[1]}")
        
    # Check Price Distribution
    cur.execute("SELECT id, metadata_json FROM products")
    prices = {}
    for row in cur.fetchall():
        pid = row[0]
        meta_str = row[1]
        price = "None"
        if meta_str:
            try:
                meta = json.loads(meta_str)
                # Check various price fields
                p_usd = meta.get('price_usd')
                p_str = meta.get('price')
                p_num = meta.get('price_numeric')
                p_disp = meta.get('price_display')
                
                # Determine what price is effectively used
                if p_usd: price = str(p_usd)
                elif p_str: price = str(p_str)
                elif p_num: price = str(p_num)
                
                # If price is 179, print it
                if "179" in str(price):
                    print(f"Found 179 price in product {pid}: {price}")
                    
            except:
                pass
        prices[price] = prices.get(price, 0) + 1
        
    print("\n--- Price Distribution ---")
    for p, c in prices.items():
        print(f"Price {p}: {c}")

if __name__ == "__main__":
    main()
