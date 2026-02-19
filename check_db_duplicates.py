import sqlite3
import json

def check_duplicates():
    conn = sqlite3.connect('data/ledger.db')
    cursor = conn.cursor()
    
    # Check for duplicate topics
    cursor.execute('SELECT id, topic, status FROM products')
    all_rows = cursor.fetchall()
    db_ids = {r[0] for r in all_rows}
    print(f"Total products in DB: {len(all_rows)}")
    
    import os
    outputs_dir = 'outputs'
    if os.path.exists(outputs_dir):
        output_folders = [f for f in os.listdir(outputs_dir) if os.path.isdir(os.path.join(outputs_dir, f))]
        print(f"Total folders in outputs/: {len(output_folders)}")
        for folder in output_folders:
            if folder not in db_ids:
                print(f"  - Folder NOT in DB: {folder}")
            else:
                # Find topic for this folder
                topic = next((r[1] for r in all_rows if r[0] == folder), "Unknown")
                print(f"  - Folder in DB: {folder} (Topic: {topic})")

    cursor.execute('SELECT topic, COUNT(*) as count FROM products GROUP BY topic HAVING count > 1')
    rows = cursor.fetchall()
    
    if not rows:
        print("No duplicate topics found in ledger.db")
    else:
        print(f"Found {len(rows)} duplicate topics:")
        for topic, count in rows:
            print(f"- Topic: {topic} ({count} entries)")
            
            # List the IDs for these duplicates
            cursor.execute('SELECT id, status, created_at FROM products WHERE topic = ? ORDER BY created_at DESC', (topic,))
            entries = cursor.fetchall()
            for pid, status, created in entries:
                print(f"  - ID: {pid}, Status: {status}, Created: {created}")

    conn.close()

if __name__ == "__main__":
    check_duplicates()
