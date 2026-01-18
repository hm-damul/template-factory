#!/usr/bin/env python3
"""
preview_generator.py - Generate preview images and thumbnails for templates

This module creates:
- HTML preview pages with styled content
- Placeholder PNG instructions (requires browser for actual PNG)
- Preview manifest for each template

Input: generated/templates/*.html, generated/products/*.json
Output: generated/previews/*.html, generated/previews/manifest.json
"""

import os
import json
from datetime import datetime

PRODUCT_DIR = "generated/products"
TEMPLATE_DIR = "generated/templates"
OUT_DIR = "generated/previews"
MANIFEST_FILE = f"{OUT_DIR}/manifest.json"
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


def get_category_color(category: str) -> str:
    """Get primary color for category."""
    colors = {
        "budget": "#059669",
        "habit": "#7c3aed",
        "meal": "#ea580c",
        "study": "#2563eb",
        "general": "#374151"
    }
    return colors.get(category, "#374151")


def generate_preview_html(product: dict, template_html: str, ts: str) -> str:
    """Generate preview HTML with metadata overlay."""
    pid = product["id"]
    title = product["title"]
    price = product.get("price", 9.99)
    category = detect_category(title)
    color = get_category_color(category)
    
    # Extract just the body content from template
    body_start = template_html.find("<body")
    body_end = template_html.find("</body>")
    if body_start > 0 and body_end > 0:
        # Find the actual content start after <body...>
        content_start = template_html.find(">", body_start) + 1
        body_content = template_html[content_start:body_end]
    else:
        body_content = template_html
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Preview: {title}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    
    body {{
      font-family: system-ui, -apple-system, sans-serif;
      background: #f3f4f6;
      min-height: 100vh;
    }}
    
    .preview-banner {{
      background: linear-gradient(135deg, {color} 0%, {color}dd 100%);
      color: white;
      padding: 16px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }}
    
    .preview-banner h1 {{
      font-size: 1.25rem;
      font-weight: 600;
    }}
    
    .preview-badge {{
      background: rgba(255,255,255,0.2);
      padding: 6px 12px;
      border-radius: 20px;
      font-size: 0.875rem;
      font-weight: 500;
    }}
    
    .preview-meta {{
      background: white;
      padding: 12px 24px;
      display: flex;
      gap: 24px;
      font-size: 0.875rem;
      color: #6b7280;
      border-bottom: 1px solid #e5e7eb;
    }}
    
    .preview-meta span {{
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    
    .preview-content {{
      background: white;
      margin: 24px;
      border-radius: 12px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.08);
      overflow: hidden;
    }}
    
    .template-frame {{
      padding: 24px;
      max-width: 800px;
      margin: 0 auto;
    }}
    
    /* Reset some template styles for preview */
    .template-frame .header {{
      margin: 0 0 24px 0 !important;
      border-radius: 8px;
    }}
    
    .preview-footer {{
      background: #f9fafb;
      padding: 16px 24px;
      text-align: center;
      font-size: 0.75rem;
      color: #9ca3af;
      border-top: 1px solid #e5e7eb;
    }}
    
    .screenshot-hint {{
      background: #fef3c7;
      border: 1px solid #fcd34d;
      border-radius: 8px;
      padding: 16px;
      margin: 24px;
      font-size: 0.875rem;
      color: #92400e;
    }}
    
    .screenshot-hint code {{
      background: #fef9c3;
      padding: 2px 6px;
      border-radius: 4px;
      font-family: monospace;
    }}
  </style>
</head>
<body>
  <div class="preview-banner">
    <h1>📋 {title}</h1>
    <span class="preview-badge">{category.upper()}</span>
  </div>
  
  <div class="preview-meta">
    <span>🆔 {pid}</span>
    <span>💰 ${price}</span>
    <span>📅 {ts}</span>
  </div>
  
  <div class="preview-content">
    <div class="template-frame">
      {body_content}
    </div>
  </div>
  
  <div class="screenshot-hint">
    <strong>📸 To generate PNG preview:</strong><br>
    Use a headless browser or screenshot tool. Example with Playwright:<br>
    <code>playwright screenshot --viewport-size=800,1000 preview.html preview.png</code>
  </div>
  
  <div class="preview-footer">
    Preview generated at {ts} · Template ID: {pid}
  </div>
</body>
</html>
'''


def generate_thumbnail_placeholder(product: dict) -> str:
    """Generate a simple SVG placeholder for thumbnail."""
    pid = product["id"]
    title = product["title"][:30]
    category = detect_category(title)
    color = get_category_color(category)
    
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300" viewBox="0 0 400 300">
  <rect width="400" height="300" fill="#f3f4f6"/>
  <rect x="20" y="20" width="360" height="40" rx="4" fill="{color}"/>
  <text x="200" y="48" text-anchor="middle" fill="white" font-family="system-ui" font-size="16" font-weight="600">
    {title}
  </text>
  <rect x="20" y="80" width="360" height="200" rx="4" fill="white" stroke="#e5e7eb"/>
  <line x1="20" y1="120" x2="380" y2="120" stroke="#e5e7eb"/>
  <line x1="20" y1="160" x2="380" y2="160" stroke="#e5e7eb"/>
  <line x1="20" y1="200" x2="380" y2="200" stroke="#e5e7eb"/>
  <line x1="20" y1="240" x2="380" y2="240" stroke="#e5e7eb"/>
  <text x="200" y="150" text-anchor="middle" fill="#9ca3af" font-family="system-ui" font-size="12">
    {pid}
  </text>
</svg>'''


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    print("=" * 50)
    print("  Preview Generator")
    print("=" * 50)
    
    if not os.path.exists(PRODUCT_DIR):
        print("ERROR: Product directory not found")
        return
    
    previews = []
    created = 0
    skipped = 0
    errors = []
    
    for fn in os.listdir(PRODUCT_DIR):
        if not fn.endswith(".json"):
            continue
        
        try:
            with open(f"{PRODUCT_DIR}/{fn}", "r", encoding="utf-8") as f:
                product = json.load(f)
            
            if product.get("state") not in ["VERIFIED", "QA_PASSED"]:
                # Also accept verified state
                if product.get("state") != "VERIFIED":
                    skipped += 1
                    continue
            
            pid = product["id"]
            title = product["title"]
            
            # Check if template exists
            template_path = f"{TEMPLATE_DIR}/{pid}.html"
            if not os.path.exists(template_path):
                skipped += 1
                continue
            
            with open(template_path, "r", encoding="utf-8") as f:
                template_html = f.read()
            
            # Generate preview HTML
            preview_html = generate_preview_html(product, template_html, ts)
            preview_path = f"{OUT_DIR}/{pid}_preview.html"
            with open(preview_path, "w", encoding="utf-8") as f:
                f.write(preview_html)
            
            # Generate SVG placeholder
            svg = generate_thumbnail_placeholder(product)
            svg_path = f"{OUT_DIR}/{pid}_thumb.svg"
            with open(svg_path, "w", encoding="utf-8") as f:
                f.write(svg)
            
            previews.append({
                "id": pid,
                "title": title,
                "category": detect_category(title),
                "preview_html": preview_path,
                "thumbnail_svg": svg_path,
                "png_status": "pending",
                "png_instructions": "Use headless browser to generate PNG from preview HTML"
            })
            
            print(f"✓ {title}")
            created += 1
            
        except Exception as e:
            errors.append({"file": fn, "error": str(e)})
            print(f"✗ {fn}: {e}")
    
    # Write manifest
    manifest = {
        "generated_at": ts,
        "previews": previews,
        "total": len(previews),
        "png_generation": {
            "status": "manual",
            "instructions": [
                "Install Playwright: pip install playwright && playwright install chromium",
                "For each preview, run:",
                "  playwright screenshot --viewport-size=800,1000 {preview_html} {output.png}",
                "Or use any headless browser automation tool"
            ]
        }
    }
    
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    # Write summary
    summary = {
        "step": "preview_generator",
        "timestamp": ts,
        "status": "success" if not errors else "partial",
        "stats": {
            "created": created,
            "skipped": skipped,
            "errors": len(errors)
        },
        "outputs": {
            "previews_dir": OUT_DIR,
            "manifest": MANIFEST_FILE
        },
        "errors": errors
    }
    
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print()
    print(f"previews_created={created} skipped={skipped} errors={len(errors)}")
    print(f"manifest={MANIFEST_FILE}")


if __name__ == "__main__":
    main()
