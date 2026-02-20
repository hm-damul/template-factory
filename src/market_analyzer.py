# -*- coding: utf-8 -*-
import json
import re
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, List

from src.product_generator import _render_landing_html_from_schema

logger = logging.getLogger(__name__)

class MarketAnalyzer:
    """
    Simulates a market analysis bot that categorizes products and optimizes pricing
    based on current market trends (simulated logic).
    """

    # 2025 Market Analysis Data
    PRICING_RULES = [
        {
            "category": "SaaS / System",
            "keywords": ["saas", "boilerplate", "system", "platform", "checkout", "revenue", "automation", "api", "merchant", "software", "tool"],
            "market_price": 179,
            "our_price": 59,
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

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.outputs_dir = project_root / "outputs"

    def analyze_market(self, title: str, category: str) -> Dict[str, Any]:
        """
        Analyzes the market for a given title and category.
        Returns a dictionary with pricing information.
        """
        cat, market_price, our_price = self.determine_category_and_price("", title, category)
        return {
            "average_price": float(market_price),
            "high_price": float(market_price * 1.5),
            "our_price": float(our_price),
            "category": cat
        }

    def get_wei_price(self, price_usd: float) -> int:
        """Calculates Wei price based on USD ($1 = 0.0004 ETH @ $2500/ETH)"""
        # 1 ETH = $2500 -> $1 = 0.0004 ETH
        # 0.0004 ETH = 4 * 10^-4 * 10^18 Wei = 4 * 10^14 Wei
        return int(price_usd * 4 * 1e14)

    def determine_category_and_price(self, product_id: str, title: str, description: str) -> Tuple[str, int, int]:
        """Returns (Category, Market Price, Our Price)"""
        text = (product_id + " " + title + " " + description).lower()
        
        for rule in self.PRICING_RULES:
            for kw in rule["keywords"]:
                if kw in text:
                    return rule["category"], rule["market_price"], rule["our_price"]
        
        return "Standard Digital Product", self.DEFAULT_MARKET_PRICE, self.DEFAULT_OUR_PRICE

    def analyze_and_optimize(self, force: bool = False) -> Tuple[Dict[str, int], List[str]]:
        """
        Scans all products in outputs_dir and updates their pricing 
        if it doesn't match the market optimized price.
        Returns a summary of updates and a list of updated product IDs.
        """
        if not self.outputs_dir.exists():
            logger.warning(f"Outputs directory not found: {self.outputs_dir}")
            return {}, []

        stats = {}
        updated_ids = []
        updates_count = 0
        
        logger.info("Starting Market Analysis and Price Optimization...")

        for product_dir in self.outputs_dir.iterdir():
            if not product_dir.is_dir():
                continue
                
            updated_cat = self._optimize_product(product_dir, force=force)
            if updated_cat:
                stats[updated_cat] = stats.get(updated_cat, 0) + 1
                updated_ids.append(product_dir.name)
                updates_count += 1
        
        if updates_count > 0:
            logger.info(f"Market Analysis Complete. Optimized {updates_count} products.")
        else:
            logger.info("Market Analysis Complete. All prices are optimal.")
            
        return stats, updated_ids

    def _optimize_product(self, product_dir: Path, force: bool = False) -> str:
        product_id = product_dir.name
        title = ""
        description = ""
        
        schema_path = product_dir / "product_schema.json"
        
        # 1. Read Metadata
        if schema_path.exists():
            try:
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                title = schema.get("title", "")
                description = schema.get("value_proposition", "")
                
                # Check if price is already optimized
                current_price_str = schema.get("sections", {}).get("pricing", {}).get("price", "$0")
                current_val = float(re.sub(r'[^\d.]', '', current_price_str))
            except Exception:
                current_val = 0
                schema = {}
        else:
            current_val = 0
            schema = {}
            
        # 2. Determine Optimal Price
        category, market_price, our_price = self.determine_category_and_price(product_id, title, description)
        
        # 3. Update if needed
        # Update if current price is not our optimal price (allow small float diff)
        if not force and abs(current_val - our_price) < 0.1:
            return None # Already optimal

        new_price_str = f"${our_price}.00"
        new_price_wei = self.get_wei_price(our_price)
        
        logger.info(f"Optimizing {product_id}: ${current_val} -> {new_price_str} ({category})")

        # 4. Apply Updates
        self._update_files(product_dir, our_price, market_price, new_price_str, new_price_wei, schema)
        
        return category

    def _update_files(self, product_dir: Path, our_price: float, market_price: float, price_str: str, price_wei: int, schema: Dict[str, Any]):
        # Update product_schema.json
        schema_path = product_dir / "product_schema.json"
        
        # Update schema object in memory
        if "sections" not in schema: schema["sections"] = {}
        if "pricing" not in schema["sections"]: schema["sections"]["pricing"] = {}
        
        schema["sections"]["pricing"]["price"] = price_str
        schema["_injected_price"] = price_str
        schema["_market_price"] = f"${market_price}.00"
        
        # Update root price for consistency
        schema["price"] = str(our_price)
        
        # Update offers price for Schema.org consistency
        if "offers" in schema:
            schema["offers"]["price"] = f"{our_price}.00"
        
        # Save updated schema
        if schema_path.exists():
            try:
                schema_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception as e:
                logger.error(f"Error updating schema for {product_dir.name}: {e}")

        # Update manifest.json
        manifest_path = product_dir / "manifest.json"
        if manifest_path.exists():
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                data["price_usd"] = our_price
                data["price"] = our_price
                data["market_price"] = market_price
                manifest_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception as e:
                logger.error(f"Error updating manifest for {product_dir.name}: {e}")

        # Regenerate index.html using the generator
        index_path = product_dir / "index.html"
        try:
            # Use the generator to create fresh HTML with new prices
            html_content = _render_landing_html_from_schema(schema)
            index_path.write_text(html_content, encoding="utf-8")
        except Exception as e:
            logger.error(f"Error regenerating index.html for {product_dir.name}: {e}")

        # Update sales_page_copy.md (and other promotions)
        self._update_promotions(product_dir, our_price, market_price, price_str)

    def _update_promotions(self, product_dir: Path, our_price: float, market_price: float, price_str: str):
        promos_dir = product_dir / "promotions"
        if not promos_dir.exists():
            return

        savings = market_price - our_price
        our_price_eth = self.get_wei_price(our_price) / 1e18

        for f in promos_dir.iterdir():
            if f.suffix in ['.html', '.md', '.txt', '.json']:
                try:
                    content = f.read_text(encoding="utf-8")
                    original_content = content
                    
                    # Regex Replacements for common patterns in copy
                    # Replace old prices ($59, $179, etc.) with new price
                    # Be specific to avoid replacing random numbers
                    
                    # Replace specific previous price points
                    content = re.sub(r"\$59(\.00)?", price_str, content)
                    content = re.sub(r"\$179(\.00)?", price_str, content)
                    content = re.sub(r"\$49(\.00)?", price_str, content)
                    
                    # Update JSON-like values
                    content = re.sub(r"59\.00", f"{our_price}.00", content)
                    
                    # Update ETH price (approximate previous value)
                    content = re.sub(r"0\.0236", f"{our_price_eth:.4f}", content)
                    
                    # Update Market Price in comparison tables
                    # Pattern: <td>Standard Digital Asset</td> <td>$179.00</td>
                    content = re.sub(r"(<td>Standard Digital Asset</td>\s*<td>\$)([\d.]+)(</td>)", 
                                     f"\\g<1>{market_price}.00\\g<3>", content)
                    
                    # Update Savings
                    # Pattern: Save $120.00 USD
                    content = re.sub(r"(Save \$)([-\d\.]+)( USD)", f"\\g<1>{savings}.00\\g<3>", content)
                    
                    if content != original_content:
                        f.write_text(content, encoding="utf-8")
                except Exception as e:
                    logger.error(f"Error updating promo {f.name}: {e}")
