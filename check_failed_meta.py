import sqlite3
import json

db_path = "data/ledger.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

product_id = "20260213-154551-프리랜서-컨설턴트-서비스-소개-랜딩-페이지"
cursor.execute("SELECT status, metadata_json FROM products WHERE id = ?", (product_id,))
row = cursor.fetchone()

if row:
    status, meta_json = row
    print(f"Status: {status}")
    print(f"Metadata: {json.dumps(json.loads(meta_json), indent=2, ensure_ascii=False)}")
else:
    print("Product not found")

conn.close()
