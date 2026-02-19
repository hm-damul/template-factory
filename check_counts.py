import os

outputs_dir = "d:/auto/MetaPassiveIncome_FINAL/outputs"
dirs = [d for d in os.listdir(outputs_dir) if os.path.isdir(os.path.join(outputs_dir, d))]
print(f"Total directories in outputs: {len(dirs)}")

# Also verify ledger count
import sqlite3
db_path = "d:/auto/MetaPassiveIncome_FINAL/data/ledger.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM products")
count = cursor.fetchone()[0]
print(f"Total products in ledger: {count}")
conn.close()