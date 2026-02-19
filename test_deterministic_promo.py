import hashlib
import random
import os
from pathlib import Path
from promotion_factory import generate_promotions

def test_deterministic_generation():
    product_id = "20260214-130903-ai-trading-bot"
    title = "AI Trading Bot Pro"
    topic = "AI trading"
    price_usd = 49.0
    
    # Create a temporary product directory structure
    base_dir = Path("d:/auto/MetaPassiveIncome_FINAL/outputs")
    product_dir = base_dir / product_id
    product_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Testing deterministic generation for: {product_id}")
    
    # Run first time
    meta1 = generate_promotions(product_dir, product_id, title, topic, price_usd)
    blog_path = product_dir / "promotions" / "blog_longform.md"
    blog1 = blog_path.read_text(encoding="utf-8")
    
    # Run second time
    meta2 = generate_promotions(product_dir, product_id, title, topic, price_usd)
    blog2 = blog_path.read_text(encoding="utf-8")
    
    if blog1 == blog2:
        print("SUCCESS: Blog content is identical for the same product_id.")
    else:
        print("FAILURE: Blog content differs for the same product_id!")
        # Check why it might differ (seed reset logic)
        print(f"Meta 1 validation: {meta1.get('validation', {}).get('score')}")
        print(f"Meta 2 validation: {meta2.get('validation', {}).get('score')}")

    # Check images
    img1 = [line for line in blog1.split('\n') if '![' in line]
    img2 = [line for line in blog2.split('\n') if '![' in line]
    
    print(f"Images found: {img1}")
    if img1 == img2:
        print("SUCCESS: Images are consistent.")
    else:
        print("FAILURE: Images differ!")

if __name__ == "__main__":
    print("--- START ---")
    try:
        test_deterministic_generation()
    except Exception as e:
        import traceback
        traceback.print_exc()
    print("--- END ---")
