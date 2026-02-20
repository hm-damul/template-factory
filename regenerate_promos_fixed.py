# -*- coding: utf-8 -*-
import sys
from pathlib import Path
import json
import logging

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT))

from src.ledger_manager import LedgerManager
from promotion_factory import generate_promotions
from promotion_dispatcher import build_channel_payloads

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def regenerate_all_promotions_strict():
    outputs_dir = PROJECT_ROOT / "outputs"
    if not outputs_dir.exists():
        logger.error("outputs directory not found.")
        return

    product_dirs = [d for d in outputs_dir.iterdir() if d.is_dir()]
    logger.info(f"Found {len(product_dirs)} product directories.")

    success_count = 0
    for p_dir in product_dirs:
        product_id = p_dir.name
        schema_path = p_dir / "product_schema.json"
        manifest_path = p_dir / "manifest.json"
        
        # Determine the CORRECT price from product_schema.json (Source of Truth)
        price_usd = 29.00
        title = "Digital Asset"
        topic = "Crypto Automation"
        
        # 1. Try schema first
        if schema_path.exists():
            try:
                with open(schema_path, 'r', encoding='utf-8') as f:
                    schema = json.load(f)
                    title = schema.get("title", title)
                    topic = schema.get("sections", {}).get("hero", {}).get("subheadline", topic)
                    
                    # Get price
                    p_str = schema.get("sections", {}).get("pricing", {}).get("price", "")
                    if p_str:
                        try:
                            price_usd = float(p_str.replace("$", "").replace(",", ""))
                        except:
                            pass
            except Exception as e:
                logger.error(f"[{product_id}] Error reading schema: {e}")
        
        # 2. Fallback to manifest if schema failed or missing
        elif manifest_path.exists():
             try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                    title = manifest.get("title", title)
                    topic = manifest.get("topic", topic)
                    if "metadata" in manifest and "final_price_usd" in manifest["metadata"]:
                        price_usd = float(manifest["metadata"]["final_price_usd"])
                    elif "product" in manifest and "price_usd" in manifest["product"]:
                        price_usd = float(manifest["product"]["price_usd"])
             except Exception as e:
                logger.error(f"[{product_id}] Error reading manifest: {e}")

        logger.info(f"[{product_id}] Regenerating promos. Price: ${price_usd:.2f}, Title: {title}")
        
        try:
            # 1. Generate markdown assets (uses price_usd in text)
            generate_promotions(
                product_dir=p_dir,
                product_id=product_id,
                title=title,
                topic=topic,
                price_usd=price_usd
            )
            
            # 2. Generate HTML (uses schema internally for table, but markdown for body)
            payloads = build_channel_payloads(product_id)
            
            # Save blog_post.html
            if "blog" in payloads and "html" in payloads["blog"]:
                blog_html = payloads["blog"]["html"]
                promotions_dir = p_dir / "promotions"
                promotions_dir.mkdir(parents=True, exist_ok=True)
                (promotions_dir / "blog_post.html").write_text(blog_html, encoding="utf-8")
                logger.info(f"[{product_id}] Saved blog_post.html")
            
            success_count += 1
        except Exception as e:
            logger.error(f"[{product_id}] Failed to regenerate: {e}")

    logger.info(f"Successfully regenerated promotions for {success_count} products.")

if __name__ == "__main__":
    regenerate_all_promotions_strict()
