import sqlite3

db_path = "d:/auto/MetaPassiveIncome_FINAL/data/ledger.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get distinct statuses
cursor.execute("SELECT DISTINCT status FROM products")
statuses = cursor.fetchall()
print("Distinct statuses in products table:")
for status in statuses:
    print(status[0])

# Get count per status
cursor.execute("SELECT status, COUNT(*) FROM products GROUP BY status")
counts = cursor.fetchall()
print("\nCount per status:")
for status, count in counts:
    print(f"{status}: {count}")
    
conn.close()