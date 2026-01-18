#!/usr/bin/env python3
"""
template_scaffolder.py - Generate production-ready template HTML with theming

This module creates professional, print-ready templates with:
- Category-specific layouts and content
- Theme-aware styling from design tokens
- Professional typography and spacing
- Print-optimized CSS

Input: generated/products/*.json, generated/design/themes/*.json
Output: generated/templates/*.html, generated/templates/summary.json
"""

import os
import json
from datetime import datetime

PRODUCT_DIR = "generated/products"
THEMES_DIR = "generated/design/themes"
OUT_DIR = "generated/templates"
SUMMARY_FILE = f"{OUT_DIR}/summary.json"


def load_theme(category: str) -> dict:
    """Load theme for category, fallback to general."""
    theme_file = f"{THEMES_DIR}/{category}.json"
    if not os.path.exists(theme_file):
        theme_file = f"{THEMES_DIR}/general.json"
    
    if os.path.exists(theme_file):
        with open(theme_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    # Fallback minimal theme
    return {
        "name": "Fallback",
        "palette": {
            "primary": "#374151",
            "onPrimary": "#ffffff",
            "secondary": "#f3f4f6",
            "onSecondary": "#1f2937",
            "accent": "#6366f1",
            "background": "#ffffff",
            "surface": "#f9fafb",
            "text": "#1f2937",
            "border": "#d1d5db"
        }
    }


def detect_category(title: str) -> str:
    """Detect category from product title."""
    t = title.lower()
    if "budget" in t or "expense" in t or "finance" in t:
        return "budget"
    if "habit" in t or "routine" in t or "tracker" in t:
        return "habit"
    if "meal" in t or "grocery" in t or "food" in t:
        return "meal"
    if "study" in t or "student" in t or "learning" in t:
        return "study"
    return "general"


def get_category_sections(category: str, title: str) -> dict:
    """Get category-specific sections and content."""
    base_sections = {
        "overview": {
            "title": "Overview",
            "content": "A professional template designed to help you organize and track your progress effectively."
        },
        "howToUse": {
            "title": "How to Use",
            "steps": [
                "Download and open the template in your preferred application",
                "Customize the fields to match your specific needs",
                "Fill in your data weekly and review monthly",
                "Print or use digitally for best results"
            ]
        }
    }
    
    category_sections = {
        "budget": {
            "mainTable": {
                "title": "Monthly Budget Tracker",
                "headers": ["Category", "Planned", "Actual", "Difference", "Notes"],
                "rows": [
                    ["Income", "", "", "", ""],
                    ["Housing", "", "", "", ""],
                    ["Utilities", "", "", "", ""],
                    ["Food", "", "", "", ""],
                    ["Transportation", "", "", "", ""],
                    ["Entertainment", "", "", "", ""],
                    ["Savings", "", "", "", ""],
                    ["Other", "", "", "", ""],
                    ["<strong>Total</strong>", "", "", "", ""]
                ]
            },
            "extras": [
                {"title": "Financial Goals", "type": "checklist", "items": ["Emergency fund", "Debt payoff", "Savings target", "Investment"]},
                {"title": "Notes & Reminders", "type": "textarea"}
            ]
        },
        "habit": {
            "mainTable": {
                "title": "Weekly Habit Tracker",
                "headers": ["Habit", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                "rows": [
                    ["Morning routine", "", "", "", "", "", "", ""],
                    ["Exercise", "", "", "", "", "", "", ""],
                    ["Reading", "", "", "", "", "", "", ""],
                    ["Meditation", "", "", "", "", "", "", ""],
                    ["Water intake", "", "", "", "", "", "", ""],
                    ["Sleep 8 hours", "", "", "", "", "", "", ""],
                    ["No screen before bed", "", "", "", "", "", "", ""]
                ]
            },
            "extras": [
                {"title": "Weekly Reflection", "type": "textarea"},
                {"title": "Goals for Next Week", "type": "checklist", "items": ["Goal 1", "Goal 2", "Goal 3"]}
            ]
        },
        "meal": {
            "mainTable": {
                "title": "Weekly Meal Planner",
                "headers": ["Day", "Breakfast", "Lunch", "Dinner", "Snacks"],
                "rows": [
                    ["Monday", "", "", "", ""],
                    ["Tuesday", "", "", "", ""],
                    ["Wednesday", "", "", "", ""],
                    ["Thursday", "", "", "", ""],
                    ["Friday", "", "", "", ""],
                    ["Saturday", "", "", "", ""],
                    ["Sunday", "", "", "", ""]
                ]
            },
            "extras": [
                {"title": "Grocery List", "type": "checklist", "items": ["Produce", "Protein", "Dairy", "Grains", "Pantry"]},
                {"title": "Meal Prep Notes", "type": "textarea"}
            ]
        },
        "study": {
            "mainTable": {
                "title": "Study Schedule",
                "headers": ["Subject", "Mon", "Tue", "Wed", "Thu", "Fri", "Hours"],
                "rows": [
                    ["Subject 1", "", "", "", "", "", ""],
                    ["Subject 2", "", "", "", "", "", ""],
                    ["Subject 3", "", "", "", "", "", ""],
                    ["Subject 4", "", "", "", "", "", ""],
                    ["Review", "", "", "", "", "", ""],
                    ["<strong>Total</strong>", "", "", "", "", "", ""]
                ]
            },
            "extras": [
                {"title": "Learning Goals", "type": "checklist", "items": ["Complete chapter", "Practice problems", "Review notes", "Quiz prep"]},
                {"title": "Study Notes", "type": "textarea"}
            ]
        }
    }
    
    sections = {**base_sections}
    if category in category_sections:
        sections.update(category_sections[category])
    else:
        # General fallback
        sections["mainTable"] = {
            "title": "Monthly Tracker",
            "headers": ["Week", "Goal", "Progress", "Result", "Notes"],
            "rows": [
                ["Week 1", "", "", "", ""],
                ["Week 2", "", "", "", ""],
                ["Week 3", "", "", "", ""],
                ["Week 4", "", "", "", ""]
            ]
        }
        sections["extras"] = [
            {"title": "Notes", "type": "textarea"}
        ]
    
    return sections


def generate_css(theme: dict) -> str:
    """Generate CSS from theme."""
    p = theme.get("palette", {})
    
    return f"""
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    
    body {{
      font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
      font-size: 14px;
      line-height: 1.5;
      color: {p.get('text', '#1f2937')};
      background: {p.get('background', '#ffffff')};
      padding: 24px;
      max-width: 800px;
      margin: 0 auto;
    }}
    
    .header {{
      background: {p.get('primary', '#374151')};
      color: {p.get('onPrimary', '#ffffff')};
      padding: 20px 24px;
      margin: -24px -24px 24px -24px;
    }}
    
    .header h1 {{
      font-size: 1.75rem;
      font-weight: 700;
      margin-bottom: 4px;
    }}
    
    .header .meta {{
      font-size: 0.875rem;
      opacity: 0.9;
    }}
    
    h2 {{
      color: {p.get('primary', '#374151')};
      font-size: 1.25rem;
      font-weight: 600;
      margin: 24px 0 12px 0;
      padding-bottom: 8px;
      border-bottom: 2px solid {p.get('border', '#d1d5db')};
    }}
    
    .overview {{
      background: {p.get('surface', '#f9fafb')};
      padding: 16px;
      border-radius: 8px;
      margin-bottom: 20px;
    }}
    
    .steps {{
      padding-left: 20px;
    }}
    
    .steps li {{
      margin-bottom: 8px;
    }}
    
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 16px 0;
    }}
    
    th {{
      background: {p.get('secondary', '#f3f4f6')};
      color: {p.get('onSecondary', '#1f2937')};
      font-weight: 600;
      text-align: left;
      padding: 10px 12px;
      border: 1px solid {p.get('border', '#d1d5db')};
    }}
    
    td {{
      padding: 10px 12px;
      border: 1px solid {p.get('border', '#d1d5db')};
      min-height: 40px;
    }}
    
    tr:nth-child(even) td {{
      background: {p.get('surface', '#f9fafb')};
    }}
    
    .extra-section {{
      background: {p.get('surface', '#f9fafb')};
      padding: 16px;
      border-radius: 8px;
      margin: 16px 0;
    }}
    
    .extra-section h3 {{
      font-size: 1rem;
      font-weight: 600;
      color: {p.get('primary', '#374151')};
      margin-bottom: 12px;
    }}
    
    .checklist {{
      list-style: none;
      padding: 0;
    }}
    
    .checklist li {{
      display: flex;
      align-items: center;
      margin-bottom: 8px;
    }}
    
    .checklist li::before {{
      content: "☐";
      margin-right: 8px;
      font-size: 1.1em;
    }}
    
    .textarea-placeholder {{
      background: #fff;
      border: 1px solid {p.get('border', '#d1d5db')};
      border-radius: 4px;
      min-height: 80px;
      padding: 8px;
    }}
    
    .footer {{
      margin-top: 32px;
      padding-top: 16px;
      border-top: 1px solid {p.get('border', '#d1d5db')};
      font-size: 0.75rem;
      color: {p.get('text', '#1f2937')};
      opacity: 0.7;
      text-align: center;
    }}
    
    @media print {{
      body {{
        padding: 0;
        max-width: none;
      }}
      .header {{
        margin: 0 0 20px 0;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
      }}
      table {{ page-break-inside: avoid; }}
      .extra-section {{ page-break-inside: avoid; }}
    }}
    """


def generate_html(product: dict, theme: dict, sections: dict, ts: str) -> str:
    """Generate complete HTML template."""
    pid = product["id"]
    title = product["title"]
    price = product.get("price", 9.99)
    
    css = generate_css(theme)
    
    # Build sections HTML
    sections_html = []
    
    # Overview
    if "overview" in sections:
        sections_html.append(f'''
    <section class="overview">
      <h2>{sections["overview"]["title"]}</h2>
      <p>{sections["overview"]["content"]}</p>
    </section>
        ''')
    
    # How to Use
    if "howToUse" in sections:
        steps_li = "\n".join(f"      <li>{step}</li>" for step in sections["howToUse"]["steps"])
        sections_html.append(f'''
    <section>
      <h2>{sections["howToUse"]["title"]}</h2>
      <ol class="steps">
{steps_li}
      </ol>
    </section>
        ''')
    
    # Main Table
    if "mainTable" in sections:
        mt = sections["mainTable"]
        headers_th = "".join(f"<th>{h}</th>" for h in mt["headers"])
        rows_tr = []
        for row in mt["rows"]:
            cells = "".join(f"<td>{c}</td>" for c in row)
            rows_tr.append(f"      <tr>{cells}</tr>")
        rows_html = "\n".join(rows_tr)
        
        sections_html.append(f'''
    <section>
      <h2>{mt["title"]}</h2>
      <table>
        <thead>
          <tr>{headers_th}</tr>
        </thead>
        <tbody>
{rows_html}
        </tbody>
      </table>
    </section>
        ''')
    
    # Extra sections
    if "extras" in sections:
        for extra in sections["extras"]:
            if extra["type"] == "checklist":
                items_li = "\n".join(f"        <li>{item}</li>" for item in extra.get("items", []))
                sections_html.append(f'''
    <section class="extra-section">
      <h3>{extra["title"]}</h3>
      <ul class="checklist">
{items_li}
      </ul>
    </section>
                ''')
            elif extra["type"] == "textarea":
                sections_html.append(f'''
    <section class="extra-section">
      <h3>{extra["title"]}</h3>
      <div class="textarea-placeholder"></div>
    </section>
                ''')
    
    content = "\n".join(sections_html)
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>{css}
  </style>
</head>
<body>
  <header class="header">
    <h1>{title}</h1>
    <div class="meta">ID: {pid} · Generated: {ts}</div>
  </header>
  
  <main>
{content}
  </main>
  
  <footer class="footer">
    <p>Template ID: {pid} · Price: ${price} · Theme: {theme.get("name", "Default")}</p>
    <p>Print tip: Use your browser's Print → Save as PDF for a printable version.</p>
  </footer>
</body>
</html>
'''


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    print("=" * 50)
    print("  Template Scaffolder")
    print("=" * 50)
    
    if not os.path.exists(PRODUCT_DIR):
        print("ERROR: Product directory not found")
        return
    
    created = 0
    skipped = 0
    errors = []
    templates = []
    
    for fn in os.listdir(PRODUCT_DIR):
        if not fn.endswith(".json"):
            continue
        
        try:
            with open(f"{PRODUCT_DIR}/{fn}", "r", encoding="utf-8") as f:
                product = json.load(f)
            
            pid = product["id"]
            title = product["title"]
            out_path = f"{OUT_DIR}/{pid}.html"
            
            # Skip if already exists (unless you want to regenerate)
            if os.path.exists(out_path):
                skipped += 1
                continue
            
            # Detect category and load theme
            category = detect_category(title)
            theme = load_theme(category)
            
            # Get category-specific sections
            sections = get_category_sections(category, title)
            
            # Generate HTML
            html = generate_html(product, theme, sections, ts)
            
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(html)
            
            templates.append({
                "id": pid,
                "title": title,
                "category": category,
                "theme": theme.get("name", "Default"),
                "file": out_path
            })
            
            print(f"✓ {title} ({category})")
            created += 1
            
        except Exception as e:
            errors.append({"file": fn, "error": str(e)})
            print(f"✗ {fn}: {e}")
    
    # Write summary
    summary = {
        "step": "template_scaffolder",
        "timestamp": ts,
        "status": "success" if not errors else "partial",
        "stats": {
            "created": created,
            "skipped": skipped,
            "errors": len(errors)
        },
        "templates": templates,
        "errors": errors
    }
    
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print()
    print(f"templates_created={created} skipped={skipped} errors={len(errors)}")
    print(f"summary={SUMMARY_FILE}")


if __name__ == "__main__":
    main()
