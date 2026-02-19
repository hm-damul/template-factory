import os
import json
import re
from pathlib import Path
from src.ledger_manager import LedgerManager
from src.config import Config

def audit_products():
    ledger = LedgerManager()
    products = ledger.get_all_products()
    
    print(f"Total Products: {len(products)}")
    
    discrepancies = []
    
    for p in products:
        pid = p['id']
        meta = p['metadata']
        status = p['status']
        topic = p['topic']
        
        # 1. Check Metadata Price
        meta_price = meta.get('final_price_usd')
        
        # 2. Check HTML Content
        output_dir = Path(f"outputs/{pid}")
        index_path = output_dir / "index.html"
        
        html_price_pricing = "N/A"
        html_our_price = "N/A"
        
        if index_path.exists():
            content = index_path.read_text(encoding="utf-8")
            
            # Find price in Pricing section (approximate)
            # Looking for <div class="price">$179<span>
            price_match = re.search(r'<div class="price">\$([\d\.]+)<span>', content)
            if price_match:
                html_price_pricing = price_match.group(1)
            
            # Find "Our Price" in Market Analysis (if exists)
            # Looking for <div>Our Price</div><div>$59.00</div> or similar
            # Based on screenshot: <div>Our Price</div><div>$59.00</div>
            # The HTML structure might be compacted, so we search loosely
            our_price_match = re.search(r'Our Price.*?\$([\d\.]+)', content, re.DOTALL)
            if our_price_match:
                html_our_price = our_price_match.group(1)
                
        # 3. Check Promotion Status
        # Dashboard likely infers this. Let's just report the product status.
        
        # Detect Discrepancy
        issue = False
        if html_price_pricing != "N/A" and html_our_price != "N/A":
            if float(html_price_pricing) != float(html_our_price):
                issue = True
        
        if issue:
            discrepancies.append({
                "id": pid,
                "topic": topic,
                "status": status,
                "meta_price": meta_price,
                "html_pricing": html_price_pricing,
                "html_our_price": html_our_price
            })

    print(f"Found {len(discrepancies)} discrepancies.")
    for d in discrepancies:
        print(f"[{d['id']}] {d['topic']}")
        print(f"  Status: {d['status']}")
        print(f"  Meta Price: {d['meta_price']}")
        print(f"  HTML Pricing: ${d['html_pricing']}")
        print(f"  HTML Our Price: ${d['html_our_price']}")
        print("-" * 30)

    return discrepancies

if __name__ == "__main__":
    audit_products()
