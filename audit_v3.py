
import sqlite3
import os
import json
import re
from pathlib import Path

DB_PATH = r"d:\auto\MetaPassiveIncome_FINAL\data\ledger.db"

def check_structure():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables:", [t[0] for t in tables])
    
    conn.close()

def check_product_files(pid):
    base_path = Path(f"d:/auto/MetaPassiveIncome_FINAL/outputs/{pid}")
    
    print(f"\nChecking files for {pid}...")
    
    # Check promo content
    promo_path = base_path / "promo_content.txt"
    if promo_path.exists():
        content = promo_path.read_text(encoding='utf-8', errors='ignore')
        prices = re.findall(r'\$\d+(?:\.\d{2})?', content)
        print(f"Promo Content Prices: {prices}")
        print(f"Promo Snippet: {content[:200]}...")
    else:
        print("promo_content.txt not found")

    # Check product.json
    json_path = base_path / "product.json"
    if json_path.exists():
        data = json.loads(json_path.read_text(encoding='utf-8'))
        print(f"product.json Price: {data.get('price', 'N/A')}")
    else:
        print("product.json not found")
        
    # Check meta.json
    meta_path = base_path / "meta.json"
    if meta_path.exists():
        data = json.loads(meta_path.read_text(encoding='utf-8'))
        print(f"meta.json Price: {data.get('price', 'N/A')}")

if __name__ == "__main__":
    check_structure()
    # Hardcoded PID from previous run
    check_product_files("20260219-063824-top-20-b2b-ecommerce-examples")
