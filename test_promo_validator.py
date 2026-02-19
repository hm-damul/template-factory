# -*- coding: utf-8 -*-
import sys
import os

# src 디렉토리 추가
sys.path.append(os.getcwd())

from src.promotion_validator import PromotionValidator

def test_validator():
    title = "AI Trading Bot Pro"
    
    # 1. 완벽한 홍보글 샘플
    perfect_content = f"""# {title}
Meta Description: The most secure and automated AI trading bot for passive income.
Key Takeaways: Instant settlement, deterministic results, and 24/7 revenue generation.

## The Problem
Manual trading is risky and emotional. You need a blueprint for success.

### Our Solution Architecture
We use a scalable and secure turnkey solution for high-ticket monetization.

![Dashboard Preview](https://example.com/image.png)

## FAQ
Q: Is it secure?
A: Yes, we prioritize privacy and security.

## Trust & Security
Verified by blockchain experts. Risk-Free trial available.

Grab your copy now! [Get Started](https://example.com/buy)
🚀 Instant download available today.
"""
    
    # 2. 부족한 홍보글 샘플 (스키마 오류)
    poor_content = """# Title
No meta description here.
Just some text without sections.
"""

    print("--- Testing Perfect Content ---")
    res1 = PromotionValidator.validate_blog_post(perfect_content, title)
    print(f"Passed: {res1.passed}")
    print(f"Score: {res1.score}")
    print(f"Errors: {res1.schema_errors}")
    print(f"Feedback: {res1.feedback}")

    print("\n--- Testing Poor Content ---")
    res2 = PromotionValidator.validate_blog_post(poor_content, title)
    print(f"Passed: {res2.passed}")
    print(f"Score: {res2.score}")
    print(f"Errors: {res2.schema_errors}")

if __name__ == "__main__":
    test_validator()
