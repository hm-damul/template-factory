#!/usr/bin/env python3
"""
design_tokens_generator.py - Generate design tokens and theme presets

This module creates a design system with:
- Color palettes (primary, secondary, accent)
- Typography scales
- Spacing units
- Theme presets for different template categories

Input: None (generates default design system)
Output: generated/design/tokens.json, generated/design/themes/*.json
"""

import os
import json
from datetime import datetime

OUT_DIR = "generated/design"
TOKENS_FILE = f"{OUT_DIR}/tokens.json"
THEMES_DIR = f"{OUT_DIR}/themes"
SUMMARY_FILE = f"{OUT_DIR}/summary.json"


def generate_base_tokens() -> dict:
    """Generate base design tokens."""
    return {
        "colors": {
            "neutral": {
                "50": "#fafafa",
                "100": "#f5f5f5",
                "200": "#e5e5e5",
                "300": "#d4d4d4",
                "400": "#a3a3a3",
                "500": "#737373",
                "600": "#525252",
                "700": "#404040",
                "800": "#262626",
                "900": "#171717"
            },
            "white": "#ffffff",
            "black": "#000000"
        },
        "typography": {
            "fontFamilies": {
                "sans": "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
                "serif": "Georgia, 'Times New Roman', serif",
                "mono": "'SF Mono', Consolas, monospace"
            },
            "fontSizes": {
                "xs": "0.75rem",
                "sm": "0.875rem",
                "base": "1rem",
                "lg": "1.125rem",
                "xl": "1.25rem",
                "2xl": "1.5rem",
                "3xl": "1.875rem",
                "4xl": "2.25rem"
            },
            "fontWeights": {
                "normal": "400",
                "medium": "500",
                "semibold": "600",
                "bold": "700"
            },
            "lineHeights": {
                "tight": "1.25",
                "normal": "1.5",
                "relaxed": "1.75"
            }
        },
        "spacing": {
            "0": "0",
            "1": "0.25rem",
            "2": "0.5rem",
            "3": "0.75rem",
            "4": "1rem",
            "5": "1.25rem",
            "6": "1.5rem",
            "8": "2rem",
            "10": "2.5rem",
            "12": "3rem",
            "16": "4rem"
        },
        "borders": {
            "radius": {
                "none": "0",
                "sm": "0.125rem",
                "md": "0.375rem",
                "lg": "0.5rem",
                "full": "9999px"
            },
            "width": {
                "thin": "1px",
                "medium": "2px",
                "thick": "4px"
            }
        },
        "shadows": {
            "sm": "0 1px 2px rgba(0,0,0,0.05)",
            "md": "0 4px 6px rgba(0,0,0,0.1)",
            "lg": "0 10px 15px rgba(0,0,0,0.1)"
        }
    }


def generate_theme(name: str, category: str, palette: dict) -> dict:
    """Generate a theme preset for a category."""
    return {
        "name": name,
        "category": category,
        "palette": palette,
        "components": {
            "header": {
                "background": palette["primary"],
                "text": palette["onPrimary"],
                "fontFamily": "sans",
                "fontSize": "2xl",
                "fontWeight": "bold"
            },
            "table": {
                "headerBg": palette["secondary"],
                "headerText": palette["onSecondary"],
                "rowBg": palette["background"],
                "rowAltBg": palette["surface"],
                "border": palette["border"]
            },
            "section": {
                "titleColor": palette["primary"],
                "textColor": palette["text"],
                "backgroundColor": palette["background"]
            },
            "accent": {
                "background": palette["accent"],
                "text": palette["onAccent"]
            }
        },
        "print": {
            "pageSize": "A4",
            "margins": "20mm",
            "headerHeight": "15mm",
            "footerHeight": "10mm"
        }
    }


def get_category_themes() -> list[dict]:
    """Generate themes for each template category."""
    themes = [
        {
            "name": "Budget Mint",
            "category": "budget",
            "palette": {
                "primary": "#059669",
                "onPrimary": "#ffffff",
                "secondary": "#d1fae5",
                "onSecondary": "#065f46",
                "accent": "#fbbf24",
                "onAccent": "#78350f",
                "background": "#ffffff",
                "surface": "#f0fdf4",
                "text": "#1f2937",
                "border": "#a7f3d0"
            }
        },
        {
            "name": "Habit Purple",
            "category": "habit",
            "palette": {
                "primary": "#7c3aed",
                "onPrimary": "#ffffff",
                "secondary": "#ede9fe",
                "onSecondary": "#5b21b6",
                "accent": "#f472b6",
                "onAccent": "#831843",
                "background": "#ffffff",
                "surface": "#faf5ff",
                "text": "#1f2937",
                "border": "#c4b5fd"
            }
        },
        {
            "name": "Meal Orange",
            "category": "meal",
            "palette": {
                "primary": "#ea580c",
                "onPrimary": "#ffffff",
                "secondary": "#ffedd5",
                "onSecondary": "#9a3412",
                "accent": "#84cc16",
                "onAccent": "#365314",
                "background": "#ffffff",
                "surface": "#fff7ed",
                "text": "#1f2937",
                "border": "#fdba74"
            }
        },
        {
            "name": "Study Blue",
            "category": "study",
            "palette": {
                "primary": "#2563eb",
                "onPrimary": "#ffffff",
                "secondary": "#dbeafe",
                "onSecondary": "#1e40af",
                "accent": "#14b8a6",
                "onAccent": "#134e4a",
                "background": "#ffffff",
                "surface": "#eff6ff",
                "text": "#1f2937",
                "border": "#93c5fd"
            }
        },
        {
            "name": "Minimal Gray",
            "category": "general",
            "palette": {
                "primary": "#374151",
                "onPrimary": "#ffffff",
                "secondary": "#f3f4f6",
                "onSecondary": "#1f2937",
                "accent": "#6366f1",
                "onAccent": "#ffffff",
                "background": "#ffffff",
                "surface": "#f9fafb",
                "text": "#1f2937",
                "border": "#d1d5db"
            }
        }
    ]
    return themes


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(THEMES_DIR, exist_ok=True)
    
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    print("=" * 50)
    print("  Design Tokens Generator")
    print("=" * 50)
    
    # Generate base tokens
    tokens = generate_base_tokens()
    tokens["_meta"] = {
        "generated_at": ts,
        "version": "1.0"
    }
    
    with open(TOKENS_FILE, "w", encoding="utf-8") as f:
        json.dump(tokens, f, indent=2, ensure_ascii=False)
    print(f"✓ Base tokens: {TOKENS_FILE}")
    
    # Generate category themes
    category_themes = get_category_themes()
    themes_created = []
    
    for theme_data in category_themes:
        theme = generate_theme(
            theme_data["name"],
            theme_data["category"],
            theme_data["palette"]
        )
        theme["_meta"] = {"generated_at": ts}
        
        theme_file = f"{THEMES_DIR}/{theme_data['category']}.json"
        with open(theme_file, "w", encoding="utf-8") as f:
            json.dump(theme, f, indent=2, ensure_ascii=False)
        
        themes_created.append({
            "name": theme_data["name"],
            "category": theme_data["category"],
            "file": theme_file
        })
        print(f"✓ Theme: {theme_data['name']} ({theme_data['category']})")
    
    # Write summary
    summary = {
        "step": "design_tokens_generator",
        "timestamp": ts,
        "status": "success",
        "outputs": {
            "tokens_file": TOKENS_FILE,
            "themes_dir": THEMES_DIR,
            "themes_count": len(themes_created)
        },
        "themes": themes_created
    }
    
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print()
    print(f"design_tokens_created=1 themes_created={len(themes_created)}")
    print(f"summary={SUMMARY_FILE}")


if __name__ == "__main__":
    main()
