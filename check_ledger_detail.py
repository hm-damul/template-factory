import sqlite3
import json
import os

db_path = os.path.join('data', 'ledger.db')
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 모든 상태 조회
cursor.execute("SELECT id, status, topic, metadata_json FROM products ORDER BY created_at DESC LIMIT 20")
rows = cursor.fetchall()
print("\n--- Recent Products (Last 20) ---")
for row in rows:
    metadata = json.loads(row['metadata_json']) if row['metadata_json'] else {}
    wp_id = metadata.get('wp_post_id')
    deploy_url = metadata.get('deployment_url')
    print(f"ID: {row['id']}")
    print(f"  Topic: {row['topic']}")
    print(f"  Status: {row['status']}")
    print(f"  WP_ID: {wp_id}")
    print(f"  Deploy: {deploy_url}")
    print("-" * 30)

conn.close()
