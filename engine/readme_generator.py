#!/usr/bin/env python3
"""
readme_generator.py - Generate product README and how-to-use documentation

This module creates:
- README.md for each product bundle
- Usage instructions
- License information
- Support/contact info

Input: generated/products/*.json
Output: docs/downloads/{pid}/README.md, generated/readme/summary.json
"""

import os
import json
from datetime import datetime

PRODUCT_DIR = "generated/products"
DOWNLOAD_ROOT = "docs/downloads"
OUT_DIR = "generated/readme"
SUMMARY_FILE = f"{OUT_DIR}/summary.json"


def detect_category(title: str) -> str:
    """Detect category from product title."""
    t = title.lower()
    if "budget" in t:
        return "budget"
    if "habit" in t:
        return "habit"
    if "meal" in t:
        return "meal"
    if "study" in t:
        return "study"
    return "general"


def get_category_tips(category: str) -> list[str]:
    """Get category-specific tips."""
    tips = {
        "budget": [
            "Track every expense, even small ones",
            "Review your budget weekly to stay on track",
            "Set realistic savings goals",
            "Use the 50/30/20 rule: 50% needs, 30% wants, 20% savings"
        ],
        "habit": [
            "Start with just 2-3 habits, then add more",
            "Be consistent - same time each day works best",
            "Don't break the chain - mark each day",
            "Celebrate small wins to stay motivated"
        ],
        "meal": [
            "Prep ingredients on Sunday for the week",
            "Keep a running grocery list",
            "Plan around what's on sale",
            "Batch cook proteins and grains"
        ],
        "study": [
            "Use the Pomodoro technique (25 min focus, 5 min break)",
            "Review notes within 24 hours of learning",
            "Teach concepts to others to solidify understanding",
            "Take breaks - your brain needs rest to consolidate"
        ]
    }
    return tips.get(category, [
        "Use consistently for best results",
        "Review and adjust as needed",
        "Make it part of your routine"
    ])


def generate_readme(product: dict, ts: str) -> str:
    """Generate README.md content for a product."""
    pid = product["id"]
    title = product["title"]
    price = product.get("price", 9.99)
    category = detect_category(title)
    tips = get_category_tips(category)
    tips_md = "\n".join(f"- {tip}" for tip in tips)
    
    return f'''# {title}

Thank you for purchasing this template! This README will help you get started.

## 📦 What's Included

| File | Description |
|------|-------------|
| `template.csv` | Editable spreadsheet template (Excel, Google Sheets, Numbers) |
| `printable.html` | Print-ready HTML template (use browser Print → Save as PDF) |
| `instructions.txt` | Quick start guide |
| `README.md` | This file |

## 🚀 Quick Start

### Option 1: Digital (Spreadsheet)
1. Open `template.csv` with your preferred app:
   - **Excel**: File → Open
   - **Google Sheets**: File → Import → Upload
   - **Numbers**: File → Open
2. Customize the template to your needs
3. Save and use regularly

### Option 2: Print
1. Open `printable.html` in your web browser
2. Press `Ctrl+P` (or `Cmd+P` on Mac)
3. Select "Save as PDF" or print directly
4. Fill in by hand

## 💡 Tips for Success

{tips_md}

## 📝 Customization Ideas

- Add your own categories or rows
- Adjust column widths for your content
- Add color coding for different priorities
- Create multiple copies for different time periods

## ❓ FAQ

**Q: Can I modify the template?**
A: Yes! Feel free to customize it to fit your needs.

**Q: What apps can open the CSV file?**
A: Microsoft Excel, Google Sheets, Apple Numbers, LibreOffice Calc, and most spreadsheet apps.

**Q: How do I print in different sizes?**
A: Open printable.html in your browser and adjust print settings (A4, Letter, etc.)

**Q: Can I share this with others?**
A: This template is for personal use. Please don't redistribute.

## 📋 Product Details

| Property | Value |
|----------|-------|
| Product ID | `{pid}` |
| Category | {category.title()} |
| Suggested Price | ${price} |
| Generated | {ts} |

## 📄 License

This template is licensed for personal, non-commercial use only.

- ✅ Use for yourself
- ✅ Print as many copies as you need
- ✅ Modify for personal use
- ❌ Resell or redistribute
- ❌ Use for commercial purposes without permission

## 🆘 Support

If you have questions or issues:
1. Check the FAQ above
2. Review the instructions.txt file
3. Contact support at the store where you purchased

---

*Thank you for your purchase! We hope this template helps you achieve your goals.*

*Generated: {ts}*
'''


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    print("=" * 50)
    print("  README Generator")
    print("=" * 50)
    
    if not os.path.exists(PRODUCT_DIR):
        print("ERROR: Product directory not found")
        return
    
    created = 0
    skipped = 0
    errors = []
    readmes = []
    
    for fn in os.listdir(PRODUCT_DIR):
        if not fn.endswith(".json"):
            continue
        
        try:
            with open(f"{PRODUCT_DIR}/{fn}", "r", encoding="utf-8") as f:
                product = json.load(f)
            
            # Only process verified products
            if product.get("state") not in ["VERIFIED", "QA_PASSED"]:
                if product.get("state") != "VERIFIED":
                    skipped += 1
                    continue
            
            pid = product["id"]
            title = product["title"]
            
            # Check if download dir exists
            download_dir = f"{DOWNLOAD_ROOT}/{pid}"
            if not os.path.exists(download_dir):
                os.makedirs(download_dir, exist_ok=True)
            
            # Generate README
            readme_content = generate_readme(product, ts)
            readme_path = f"{download_dir}/README.md"
            
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(readme_content)
            
            readmes.append({
                "id": pid,
                "title": title,
                "category": detect_category(title),
                "file": readme_path
            })
            
            print(f"✓ {title}")
            created += 1
            
        except Exception as e:
            errors.append({"file": fn, "error": str(e)})
            print(f"✗ {fn}: {e}")
    
    # Write summary
    summary = {
        "step": "readme_generator",
        "timestamp": ts,
        "status": "success" if not errors else "partial",
        "stats": {
            "created": created,
            "skipped": skipped,
            "errors": len(errors)
        },
        "readmes": readmes,
        "errors": errors
    }
    
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print()
    print(f"readmes_created={created} skipped={skipped} errors={len(errors)}")
    print(f"summary={SUMMARY_FILE}")


if __name__ == "__main__":
    main()
