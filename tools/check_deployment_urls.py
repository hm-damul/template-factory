import os
import sys
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import create_engine, text
from src.config import Config

def check_deployment_urls():
    db_url = Config.DATABASE_URL
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
        if not os.path.exists(db_path):
            print(f"Database not found at {db_path}")
            return

    engine = create_engine(db_url)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id, status, metadata_json FROM products WHERE status='PROMOTED' LIMIT 5"))
        products = result.fetchall()
        
        print(f"Checking {len(products)} PROMOTED products for deployment_url...")
        for p in products:
            pid, status, meta_str = p
            meta = json.loads(meta_str) if meta_str else {}
            url = meta.get("deployment_url")
            print(f"Product {pid}: URL={url}")

if __name__ == "__main__":
    check_deployment_urls()
