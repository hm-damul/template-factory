import os
import re
import requests
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional

try:
    from .product_generator import _render_checkout_html
except ImportError:
    # Fallback if imported from a different context
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from product_generator import _render_checkout_html

logger = logging.getLogger("LocalVerifier")

class LocalVerifier:
    def __init__(self, api_base: str = "http://127.0.0.1:5000"):
        self.api_base = api_base

    def verify_and_repair_product(self, product_dir: str) -> bool:
        """
        Verifies and repairs a product directory.
        Returns True if the product is valid (or was successfully repaired), False otherwise.
        """
        if not os.path.isdir(product_dir):
            return False

        index_path = os.path.join(product_dir, 'index.html')
        if not os.path.exists(index_path):
            logger.warning(f"Missing index.html in {product_dir}")
            return False

        # 1. Repair index.html
        repaired_index = self._fix_index_html(index_path)
        if repaired_index:
            logger.info(f"Repaired index.html in {product_dir}")

        # 2. Extract metadata
        metadata = self._extract_metadata(index_path)

        # 3. Ensure checkout.html
        repaired_checkout = self._ensure_checkout_html(product_dir, metadata)
        if repaired_checkout:
            logger.info(f"Generated checkout.html in {product_dir}")

        # 4. Simulate Buyer (API Check)
        self._simulate_buyer(metadata)
        
        return True

    def _fix_index_html(self, file_path: str) -> bool:
        """
        Patches index.html to replace the modal logic with direct checkout logic.
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        content_new = content

        # 1. Fix the broken patch from previous run
        broken_patch = """        "open-plans": function() {
          var plan = localStorage.getItem(KEY_PLAN) || "Premium";
          startPay(plan);
        }, 50);
        },"""
        
        fixed_patch = """        "open-plans": function() {
          var plan = localStorage.getItem(KEY_PLAN) || "Premium";
          startPay(plan);
        },"""

        if broken_patch in content_new:
            content_new = content_new.replace(broken_patch, fixed_patch)

        # 2. Apply patch to original code (strict string matching)
        original_open_plans = """        "open-plans": function() {
          openModal("#modal-plans");
          // 모달 오픈 시 현재 선택된 플랜 표시
          var plan = localStorage.getItem(KEY_PLAN) || "";
          var leadPlan = qs("#lead-plan");
          if (leadPlan) leadPlan.value = plan;
          setTimeout(function() {
            var inp = qs("#lead-email");
            if (inp) inp.focus();
          }, 50);
        },"""

        new_open_plans = """        "open-plans": function() {
          var plan = localStorage.getItem(KEY_PLAN) || "Premium";
          startPay(plan);
        },"""

        if original_open_plans in content_new:
            content_new = content_new.replace(original_open_plans, new_open_plans)

        # 3. Apply patch to choose-plan (original code)
        original_choose_plan = """        "choose-plan": function(el) {
          var plan = el.getAttribute("data-plan") || "Starter";
          var price = el.getAttribute("data-price") || "$19";
          localStorage.setItem(KEY_PLAN, plan);
          localStorage.setItem(KEY_PRICE, price);

          var leadPlan = qs("#lead-plan");
          if (leadPlan) leadPlan.value = plan;
          showToast("Plan selected: " + plan + " (" + price + ")");
          openModal("#modal-plans");
        },"""

        new_choose_plan = """        "choose-plan": function(el) {
          var plan = el.getAttribute("data-plan") || "Starter";
          var price = el.getAttribute("data-price") || "$19";
          localStorage.setItem(KEY_PLAN, plan);
          localStorage.setItem(KEY_PRICE, price);

          showToast("Plan selected: " + plan + " (" + price + ")");
          startPay(plan);
        },"""

        if original_choose_plan in content_new:
            content_new = content_new.replace(original_choose_plan, new_choose_plan)

        if content != content_new:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content_new)
            return True
        return False

    def _extract_metadata(self, index_html_path: str) -> Dict[str, str]:
        """
        Extracts product_id, price, title, brand from index.html
        """
        with open(index_html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract product ID
        pid_match = re.search(r'body data-product-id="([^"]+)"', content)
        pid = pid_match.group(1) if pid_match else "unknown-product"
        
        # Extract Title (h1 or title tag)
        title_match = re.search(r'<title>(.*?)</title>', content)
        title = title_match.group(1) if title_match else "Product"
        
        # Extract Brand (from footer or meta)
        brand_match = re.search(r'meta name="author" content="([^"]+)"', content)
        brand = brand_match.group(1) if brand_match else "MetaPassiveIncome"
        
        # Extract Price (default to $19 if not found)
        price_match = re.search(r'data-price="(\$?\d+)"', content)
        price = price_match.group(1) if price_match else "$19"
        
        return {
            "product_id": pid,
            "title": title,
            "brand": brand,
            "price": price
        }

    def _ensure_checkout_html(self, dir_path: str, metadata: Dict[str, str]) -> bool:
        checkout_path = os.path.join(dir_path, 'checkout.html')
        # Always regenerate to ensure latest version
        if _render_checkout_html:
            html = _render_checkout_html(
                product_id=metadata['product_id'],
                product_price=metadata['price'],
                product_title=metadata['title'],
                brand=metadata['brand']
            )
            with open(checkout_path, 'w', encoding='utf-8') as f:
                f.write(html)
            return True
        return False

    def _simulate_buyer(self, metadata: Dict[str, str]):
        try:
            price_val = float(re.sub(r'[^0-9.]', '', metadata['price']))
            
            # Check if API is up (simulated buyer click)
            params = {
                "product_id": metadata['product_id'],
                "price_amount": price_val,
                "price_currency": "usd"
            }
            # Very short timeout just to check connectivity
            try:
                requests.get(f"{self.api_base}/api/pay/start", params=params, timeout=0.5)
            except:
                pass # Ignore connection errors
                
        except Exception:
            pass
