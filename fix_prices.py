import json
import random
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

from src.ledger_manager import LedgerManager
from src.config import Config

def fix_prices():
    print("Starting price fix...")
    lm = LedgerManager(Config.DATABASE_URL)
    session = lm.get_session()
    
    try:
        # Get all products
        from src.ledger_manager import Product
        products = session.query(Product).all()
        
        fixed_count = 0
        for p in products:
            meta = json.loads(p.metadata_json) if p.metadata_json else {}
            price = meta.get("price_usd")
            
            needs_fix = False
            if price is None:
                needs_fix = True
            else:
                try:
                    p_val = float(price)
                    if p_val <= 0:
                        needs_fix = True
                except:
                    needs_fix = True
            
            if needs_fix:
                new_price = random.choice([19.0, 29.0, 39.0, 49.0, 59.0])
                print(f"Fixing price for {p.id} ({p.topic}): {price} -> {new_price}")
                meta["price_usd"] = new_price
                p.metadata_json = json.dumps(meta)
                fixed_count += 1
        
        if fixed_count > 0:
            session.commit()
            print(f"Successfully fixed {fixed_count} products.")
        else:
            print("No products needed fixing.")
            
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    fix_prices()
