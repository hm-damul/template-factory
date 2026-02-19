
import sqlite3
import json
import logging
from pathlib import Path
from src.market_analyzer import MarketAnalyzer

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path("d:/auto/MetaPassiveIncome_FINAL")
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
DB_PATH = PROJECT_ROOT / "data" / "ledger.db"

def update_database():
    if not DB_PATH.exists():
        logger.error(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    logger.info("Syncing Database with File System...")
    updated_count = 0
    
    for product_dir in OUTPUTS_DIR.iterdir():
        if not product_dir.is_dir():
            continue
            
        pid = product_dir.name
        schema_path = product_dir / "product_schema.json"
        
        if not schema_path.exists():
            continue
            
        try:
            # Read updated schema
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            
            # Extract pricing info
            price_str = schema.get("_injected_price", "$0")
            market_price_str = schema.get("_market_price", "$0")
            
            # Parse prices
            price_usd = float(price_str.replace("$", "").replace(",", ""))
            market_price = float(market_price_str.replace("$", "").replace(",", ""))
            
            # Get Category (we can infer it or get from schema if we stored it, 
            # but schema doesn't strictly store 'category' in a standard field, 
            # maybe we should have. But we can re-derive it or just update prices.)
            
            # Update DB
            cursor.execute("SELECT metadata_json FROM products WHERE id=?", (pid,))
            row = cursor.fetchone()
            
            if row:
                meta = json.loads(row[0]) if row[0] else {}
                
                # Update fields
                meta["price_usd"] = price_usd
                meta["price"] = price_usd
                meta["market_price"] = market_price
                
                # Update DB
                cursor.execute("UPDATE products SET metadata_json=? WHERE id=?", (json.dumps(meta), pid))
                updated_count += 1
                
        except Exception as e:
            logger.error(f"Error syncing DB for {pid}: {e}")
            
    conn.commit()
    conn.close()
    logger.info(f"Database Sync Complete. Updated {updated_count} records.")

def main():
    logger.info("Starting Full Pricing Update...")
    
    # 1. Initialize Analyzer
    analyzer = MarketAnalyzer(PROJECT_ROOT)
    
    # 2. Run Analysis & File Updates (Force Update to ensure consistency)
    logger.info("Running Market Analysis & File Updates...")
    stats = analyzer.analyze_and_optimize(force=True)
    
    logger.info("File Updates Summary:")
    for cat, count in stats.items():
        logger.info(f"  - {cat}: {count}")
        
    # 3. Sync Database
    update_database()
    
    logger.info("All tasks completed successfully.")

if __name__ == "__main__":
    main()
