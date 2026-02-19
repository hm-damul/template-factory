import sqlite3
from pathlib import Path

# Connect to ledger.db
db_path = Path("data/ledger.db")
if not db_path.exists():
    print("ledger.db not found!")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Status Counts
    print("\n--- Status Counts ---")
    cursor.execute("SELECT status, COUNT(*) FROM products GROUP BY status")
    rows = cursor.fetchall()
    for row in rows:
        print(f"{row[0]}: {row[1]}")

    # Price Statistics
    print("\n--- Price Statistics (final_price_usd) ---")
    cursor.execute("SELECT final_price_usd, COUNT(*) FROM products GROUP BY final_price_usd")
    rows = cursor.fetchall()
    for row in rows:
        print(f"${row[0]}: {row[1]} products")

    # Sample Data
    print("\n--- Sample Data (first 5 rows) ---")
    cursor.execute("SELECT id, status, final_price_usd FROM products LIMIT 5")
    rows = cursor.fetchall()
    for row in rows:
        print(row)

    # Check for non-published
    print("\n--- Products with Status != 'published' ---")
    cursor.execute("SELECT id, status, final_price_usd FROM products WHERE status != 'published'")
    rows = cursor.fetchall()
    if rows:
        for row in rows:
            print(row)
    else:
        print("All products are 'published' (if count matches dashboard).")

except Exception as e:
    print(f"Error reading database: {e}")
finally:
    conn.close()
