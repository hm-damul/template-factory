import os
from pathlib import Path
import json
from src.ledger_manager import LedgerManager
from src.config import Config

def check_promotion_results():
    outputs = Path("outputs")
    promoted_count = 0
    
    print(f"📊 Checking Promotion Status for all products...")
    
    try:
        lm = LedgerManager(Config.DATABASE_URL)
        products = lm.get_all_products()
    except Exception as e:
        print(f"Error accessing ledger: {e}")
        products = []

    print(f"{'Product':<30} | {'Medium':<10} | {'Tumblr':<10} | {'GitHub':<10} | {'WP':<10}")
    print("-" * 85)

    for p in products:
        pid = p['id']
        topic = p['topic'][:28]
        meta = p.get('metadata') or {}
        
        m_status = "✅" if meta.get("medium_url") else "❌"
        t_status = "✅" if meta.get("tumblr_url") else "❌"
        g_status = "✅" if meta.get("github_pages_url") else "❌"
        w_status = "✅" if meta.get("wp_link") or meta.get("wp_post_id") else "❌"
        
        print(f"{topic:<30} | {m_status:<10} | {t_status:<10} | {g_status:<10} | {w_status:<10}")
        
        if any(s == "✅" for s in [m_status, t_status, g_status, w_status]):
            promoted_count += 1
            
    print("-" * 85)
    print(f"Total products with at least one blog promotion: {promoted_count}/{len(products)}")

if __name__ == "__main__":
    check_promotion_results()
