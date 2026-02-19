import sqlite3
import os

db_path = 'data/ledger.db'
print(f"Checking database at: {os.path.abspath(db_path)}")

if not os.path.exists(db_path):
    print("Error: Database file not found!")
    exit(1)

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # List tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("\nTables found:")
    for table in tables:
        print(f"- {table[0]}")
        
        # Get schema for each table
        print(f"  Schema for {table[0]}:")
        cursor.execute(f"PRAGMA table_info({table[0]})")
        columns = cursor.fetchall()
        for col in columns:
            print(f"    {col[1]} ({col[2]})")
            
    # Check status distribution in products table if it exists
    if ('products',) in tables:
        print("\nStatus Distribution in 'products':")
        cursor.execute("SELECT status, COUNT(*) FROM products GROUP BY status")
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]}")
            
    conn.close()

except sqlite3.Error as e:
    print(f"SQLite error: {e}")
except Exception as e:
    print(f"Error: {e}")
