
import sqlite3
import json
import os
import re
from pathlib import Path
from typing import Dict, Any, List

# Define paths
PROJECT_ROOT = Path("d:/auto/MetaPassiveIncome_FINAL")
DB_PATH = PROJECT_ROOT / "data" / "ledger.db"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

# Pricing Rules from src/market_analyzer.py (Replicated/Enhanced)
PRICING_RULES = [
    {
        "category": "SaaS / System",
        "keywords": ["saas", "boilerplate", "system", "platform", "checkout", "revenue", "automation", "api", "merchant", "software", "tool"],
        "market_price": 179,
        "our_price": 59,  # Aggressive pricing for high value
        "desc": "High-value functional software/system"
    },
    {
        "category": "Trading / Bot / Crypto Tool",
        "keywords": ["trading", "bot", "crypto", "signal", "tax", "finance", "defi", "web3", "contract", "audit", "arbitrage", "mev"],
        "market_price": 149,
        "our_price": 49,
        "desc": "Specialized financial tools & scripts"
    },
    {
        "category": "Course / Masterclass",
        "keywords": ["course", "masterclass", "training", "bootcamp", "curriculum"],
        "market_price": 99,
        "our_price": 39,
        "desc": "Comprehensive educational courses"
    },
    {
        "category": "Template / Landing Page",
        "keywords": ["landing", "template", "theme", "design", "ui", "ux", "portfolio", "component", "kit"],
        "market_price": 49,
        "our_price": 19,
        "desc": "Ready-to-use web templates"
    },
    {
        "category": "Prompt Pack / Asset",
        "keywords": ["prompt", "pack", "asset", "icon", "graphics", "bundle", "collection"],
        "market_price": 39,
        "our_price": 15,
        "desc": "Digital assets & AI prompts"
    },
    {
        "category": "Guide / E-book / Blueprint",
        "keywords": ["guide", "blueprint", "book", "pdf", "report", "marketing", "plan", "strategy", "roadmap", "checklist"],
        "market_price": 49,
        "our_price": 29,
        "desc": "Educational content & strategies"
    }
]

DEFAULT_MARKET_PRICE = 49
DEFAULT_OUR_PRICE = 29

def determine_price(title: str, topic: str) -> Dict[str, Any]:
    """
    Determines the market price and our price based on the product title/topic.
    """
    text = (title + " " + topic).lower()
    
    for rule in PRICING_RULES:
        for keyword in rule["keywords"]:
            if keyword in text:
                return {
                    "category": rule["category"],
                    "market_price": rule["market_price"],
                    "our_price": rule["our_price"],
                    "desc": rule["desc"]
                }
    
    return {
        "category": "Standard Digital Asset",
        "market_price": DEFAULT_MARKET_PRICE,
        "our_price": DEFAULT_OUR_PRICE,
        "desc": "High-quality digital resource"
    }

def update_product_files(product_id: str, price_info: Dict[str, Any]):
    """
    Updates all files for a given product with the determined price.
    """
    product_dir = OUTPUTS_DIR / product_id
    if not product_dir.exists():
        return

    market_price = price_info["market_price"]
    our_price = price_info["our_price"]
    our_price_eth = round(our_price / 2500, 6) # Assume $2500/ETH for conversion
    
    # 1. Update product_schema.json
    schema_path = product_dir / "product_schema.json"
    if schema_path.exists():
        try:
            data = json.loads(schema_path.read_text(encoding="utf-8"))
            data["_injected_price"] = f"${our_price}.00"
            data["_market_price"] = f"${market_price}.00" # Store market price if possible
            
            if "sections" in data and "pricing" in data["sections"]:
                data["sections"]["pricing"]["price"] = f"${our_price}.00"
                # If there's a place for market price/comparison, update it too
                # Assuming generic structure for now
            
            # Store full analysis in metadata-like field if exists
            data["market_analysis"] = price_info
            
            schema_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            print(f"[{product_id}] Error updating schema: {e}")

    # 2. Update manifest.json
    manifest_path = product_dir / "manifest.json"
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            data["price_usd"] = our_price
            data["price"] = our_price
            data["market_price"] = market_price
            manifest_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            print(f"[{product_id}] Error updating manifest: {e}")

    # 3. Update index.html (Regex replacement)
    index_path = product_dir / "index.html"
    if index_path.exists():
        try:
            content = index_path.read_text(encoding="utf-8")
            
            # Replace Price Tags (Generic patterns)
            # Pattern: $XX.XX or $XX
            # We need to be careful not to replace random numbers.
            # Strategy: Look for specific price markers or replace known previous values ($59, $179, etc.)
            # But "previous values" are now mostly $59. So we replace $59 with new price.
            
            # Replace specific incorrect prices we introduced or existed
            known_prices = ["$59.00", "$59", "$179.00", "$179", "$49.00", "$49", "$29.00", "$29"]
            
            # We replace them ONLY if we are sure? 
            # Better approach: We know we unified to $59. So we target $59.
            # But some might have been missed.
            
            # Re-generate pricing section? Too complex.
            # Text replacement:
            # Replace our price
            content = re.sub(r"\$59(\.00)?", f"${our_price}.00", content)
            
            # Replace market price (often strikethrough or comparison)
            # If we see a higher price that isn't our price, it might be market price.
            # Hard to regex safely.
            
            # Update Schema.org Price
            content = re.sub(r'"price": "\d+(\.\d+)?"', f'"price": "{our_price}.00"', content)
            
            # Update ETH price if present
            # 0.0236 was for $59
            content = re.sub(r"0\.0236", f"{our_price_eth:.4f}", content)
            
            index_path.write_text(content, encoding="utf-8")
        except Exception as e:
            print(f"[{product_id}] Error updating index.html: {e}")

    # 4. Update Promotions
    promos_dir = product_dir / "promotions"
    if promos_dir.exists():
        for f in promos_dir.iterdir():
            if f.suffix in ['.html', '.md', '.txt', '.json']:
                try:
                    content = f.read_text(encoding="utf-8")
                    
                    # Replace $59 with new Our Price
                    content = re.sub(r"\$59(\.00)?", f"${our_price}.00", content)
                    content = re.sub(r"59\.00", f"{our_price}.00", content)
                    
                    # Update ETH
                    content = re.sub(r"0\.0236", f"{our_price_eth:.4f}", content)
                    
                    # Update Market Price references if identifiable?
                    # "Average Market Price</td>\s*<td>\$[\d\.]+</td>"
                    # Regex to find table row for Market Price
                    # <td>Standard Digital Asset</td>\s*<td>\$(\d+\.\d+)</td>
                    # Replace the captured group with new market price
                    content = re.sub(r"(<td>Standard Digital Asset</td>\s*<td>\$)(\d+\.\d+)(</td>)", 
                                     f"\\g<1>{market_price}.00\\g<3>", content)
                    
                    # Update Savings
                    # Savings = Market - Our
                    savings = market_price - our_price
                    # "Save $XX.00 USD"
                    content = re.sub(r"(Save \$)([-\d\.]+)( USD)", f"\\g<1>{savings}.00\\g<3>", content)
                    
                    f.write_text(content, encoding="utf-8")
                except Exception as e:
                    print(f"[{product_id}] Error updating promo {f.name}: {e}")

def main():
    if not DB_PATH.exists():
        print("Database not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all products
    cursor.execute("SELECT id, topic, metadata_json FROM products")
    rows = cursor.fetchall()
    
    print(f"Found {len(rows)} products. Starting dynamic price update...")
    
    updated_count = 0
    
    for row in rows:
        pid, topic, meta_json = row
        meta = json.loads(meta_json) if meta_json else {}
        
        # Determine price
        price_info = determine_price(pid, topic) # pid often contains slug/title info
        
        # Update Metadata
        meta["price_usd"] = price_info["our_price"]
        meta["price"] = price_info["our_price"]
        meta["market_price"] = price_info["market_price"]
        meta["price_category"] = price_info["category"]
        
        # Save back to DB
        new_meta_json = json.dumps(meta)
        cursor.execute("UPDATE products SET metadata_json = ? WHERE id = ?", (new_meta_json, pid))
        
        # Update Files
        update_product_files(pid, price_info)
        
        updated_count += 1
        print(f"Updated {pid}: Category='{price_info['category']}', Price=${price_info['our_price']}")

    conn.commit()
    conn.close()
    print(f"Completed. Updated {updated_count} products.")

if __name__ == "__main__":
    main()
