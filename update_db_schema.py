
import sqlite3
import os
import sys

print("Starting DB schema update script...")
sys.stdout.flush()

db_path = r"D:\auto\MetaPassiveIncome_FINAL\data\ledger.db"
print(f"Checking DB at: {db_path}")
sys.stdout.flush()

if os.path.exists(db_path):
    print("DB file found. Connecting...")
    sys.stdout.flush()
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # content_hash 컬럼이 이미 존재하는지 확인
        cursor.execute("PRAGMA table_info(products);")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"Existing columns: {columns}")
        sys.stdout.flush()
        
        if "content_hash" not in columns:
            print("Adding content_hash column...")
            sys.stdout.flush()
            cursor.execute("ALTER TABLE products ADD COLUMN content_hash TEXT;")
            print("content_hash column added to products table.")
        else:
            print("content_hash column already exists.")
        
        conn.commit()
        conn.close()
        print("DB update completed successfully.")
    except Exception as e:
        print(f"Error updating database: {e}")
else:
    print("Database not found.")
sys.stdout.flush()
