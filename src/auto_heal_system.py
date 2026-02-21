
import logging
import json
import time
import requests
import base64
import os
from pathlib import Path
from typing import Dict, Any, List

from src.audit_bot import SystemAuditBot
from src.ledger_manager import LedgerManager
from src.config import Config
from src.error_learning_system import get_error_system
from src.payment_flow_verifier import PaymentFlowVerifier
from src.publisher import Publisher
try:
    from src import promotion_dispatcher
except ImportError:
    import promotion_dispatcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("auto_heal.log", encoding='utf-8')
    ]
)
logger = logging.getLogger("AutoHealSystem")

class AutoHealSystem:
    def __init__(self):
        self.audit_bot = SystemAuditBot()
        self.ledger = LedgerManager(Config.DATABASE_URL)
        # Use Publisher for Git-based deployment (bypassing Vercel API limits)
        self.publisher = Publisher(self.ledger)
        self.project_root = Path(__file__).parent.parent
        self.outputs_dir = self.project_root / "outputs"

    def run_full_audit_and_heal(self):
        logger.info("Starting Full System Audit and Heal Process...")
        
        # 1. Audit Products
        logger.info("Auditing Products...")
        product_audits = self.audit_bot.audit_products()
        self._heal_products(product_audits)
        
        # 2. Audit Promotions
        logger.info("Auditing Promotions...")
        promo_audits = self.audit_bot.audit_promotions()
        self._heal_promotions(promo_audits)
        
        logger.info("Auto Heal Process Completed.")

    def _heal_products(self, audits: List[Dict[str, Any]]):
        for item in audits:
            pid = item["product_id"]
            issues = item["issues"]
            status = item["status"]
            
            if not issues:
                continue
                
            logger.info(f"Found issues for product {pid}: {issues}")
            
            # Issue: Missing deployment_url or Deployment URL dead
            if any("Deployment URL dead" in i or "Missing deployment_url" in i or "Deployment URL is localhost" in i for i in issues):
                self._redeploy_product(pid)

            # Issue: Missing index.html (Cannot redeploy if source is missing, needs regeneration)
            if any("Missing index.html" in i for i in issues):
                logger.warning(f"Product {pid} is missing index.html. Regeneration needed (not implemented in auto-heal yet).")
                # Potential enhancement: Call ProductGenerator to regenerate based on topic

    def _redeploy_product(self, product_id: str):
        from src.progress_tracker import update_progress
        logger.info(f"Attempting to redeploy product {product_id}...")
        update_progress("Auto Heal", "Redeploying", 10, "Starting redeployment...", product_id)
        product_dir = self.outputs_dir / product_id
        
        if not product_dir.exists():
            logger.error(f"Cannot redeploy {product_id}: Directory not found.")
            update_progress("Auto Heal", "Failed", 0, "Product directory not found", product_id)
            return

        # Check if index.html exists
        if not (product_dir / "index.html").exists():
             logger.error(f"Cannot redeploy {product_id}: index.html missing.")
             return

        try:
            # Use Publisher for Git Push deployment
            logger.info(f"Redeploying product {product_id} using Publisher (Git Push)...")
            result = self.publisher.publish_product(product_id, str(product_dir))
            deployment_url = result.get("url")
            
            if deployment_url:
                logger.info(f"Redeployment successful: {deployment_url}")
                
                # Payment Flow Verification
                logger.info(f"Verifying payment flow for {product_id}...")
                verifier = PaymentFlowVerifier()
                
                # Get price from metadata
                prod = self.ledger.get_product(product_id)
                meta = prod.get("metadata", {}) if prod else {}
                if isinstance(meta, str):
                    meta = json.loads(meta)
                    
                try:
                    price = float(meta.get("price_usd", 1.0))
                except:
                    price = 1.0
                    
                is_verified, msg, details = verifier.verify_payment_flow(product_id, deployment_url, price)
                
                if is_verified:
                    logger.info(f"Payment flow verified: {msg}")
                    verification_meta = {
                        "payment_verified": True,
                        "verification_details": details
                    }
                else:
                    logger.error(f"Payment flow verification failed: {msg}")
                    verification_meta = {
                        "payment_verified": False,
                        "verification_error": msg,
                        "verification_details": details
                    }

                # Update Ledger
                # Check current status first to avoid overwriting SOLD status
                current_status = prod.get("status")
                new_status = "PUBLISHED"
                if current_status == "SOLD":
                    new_status = "SOLD"
                elif not is_verified:
                    # If payment verification failed, mark as FAILED to prevent promotion of broken product
                    new_status = "PUBLISH_FAILED"
                
                self.ledger.update_product_status(product_id, new_status, metadata={
                    "deployment_url": deployment_url, 
                    "deploy_method": "git_push_auto_heal",
                    **verification_meta
                })
            else:
                logger.error(f"Redeployment failed for {product_id}")
                update_progress("Auto Heal", "Failed", 0, "Deployment returned no URL", product_id)
        except Exception as e:
            logger.error(f"Redeployment exception for {product_id}: {e}")
            update_progress("Auto Heal", "Failed", 0, f"Exception: {str(e)}", product_id)
            
            # AI Error Analysis and Fix
            try:
                error_system = get_error_system()
                analysis = error_system.analyze_and_fix(e, context=f"Redeploying product {product_id}")
                if analysis.get("confidence", 0) > 0.8:
                    logger.info(f"AI Suggested Fix: {analysis.get('details')}")
                    if error_system.apply_fix(analysis):
                         logger.info("Auto-fix applied successfully.")
            except Exception as ai_e:
                logger.error(f"AI Error Analysis failed: {ai_e}")

    def _heal_promotions(self, audits: List[Dict[str, Any]]):
        for item in audits:
            pid = item["product_id"]
            issues = item["issues"]
            post_id = item.get("post_id")
            
            if not issues:
                continue
                
            logger.info(f"Found promotion issues for product {pid} (Post {post_id}): {issues}")
            
            # Issue: No product link found or Broken product link
            if any("No link to" in i or "No product link" in i for i in issues):
                self._fix_wp_post_link(pid, post_id)

    def _fix_wp_post_link(self, product_id: str, post_id: str):
        logger.info(f"Attempting to fix WordPress post {post_id} for product {product_id}...")
        
        # 1. Get Product Info
        prod = self.ledger.get_product(product_id)
        if not prod:
            logger.error(f"Product {product_id} not found in ledger.")
            return
            
        meta = prod.get("metadata", {})
        if isinstance(meta, str):
            meta = json.loads(meta)
            
        deployment_url = meta.get("deployment_url")
        if not deployment_url:
            logger.error(f"Product {product_id} has no deployment_url. Cannot fix link.")
            return
            
        title = meta.get("title") or prod.get("topic")
        price = meta.get("price_usd") or "29.00"
        
        # 2. Load Blog Content (Markdown)
        promo_dir = self.outputs_dir / product_id / "promotions"
        blog_md_path = promo_dir / "blog_longform.md"
        if not blog_md_path.exists():
            blog_md_path = promo_dir / "blog_post.md"
            
        if not blog_md_path.exists():
            logger.error(f"Markdown content not found for {product_id}.")
            return
            
        blog_md = blog_md_path.read_text(encoding="utf-8", errors="ignore")
        
        # 3. Regenerate HTML with correct link
        # We need to replace (#) with the actual URL in the markdown first if it's generic
        if "(#)" in blog_md:
            blog_md = blog_md.replace("(#)", f"({deployment_url})")
        if "(# \"" in blog_md:
             blog_md = blog_md.replace("(# \"", f"({deployment_url} \"")
        if "](#)" in blog_md:
             blog_md = blog_md.replace("](#)", f"]({deployment_url})")
             
        # Also, check if we need to force insert the link if it's missing entirely
        if deployment_url not in blog_md:
             # Append a CTA
             blog_md += f"\n\n## Get Instant Access\n\n[Download {title} Now]({deployment_url})"
        
        # Regenerate HTML using the fixed promotion_dispatcher function
        try:
            html_content = promotion_dispatcher._simple_markdown_to_html(
                blog_md, 
                title=title, 
                target_url=deployment_url, 
                price=str(price),
                product_id=product_id
            )
        except Exception as e:
            logger.error(f"HTML generation failed: {e}")
            return

        # 4. Update WordPress Post
        # Load Config
        cfg = promotion_dispatcher.load_channel_config()
        wp_cfg = cfg.get("blog", {})
        wp_api_url = wp_cfg.get("wp_api_url")
        wp_token = wp_cfg.get("wp_token")
        
        if not wp_api_url or not wp_token:
            logger.error("WordPress config missing.")
            return
            
        # Update
        self._update_wp_post(wp_api_url, wp_token, post_id, html_content)

    def _update_wp_post(self, api_url: str, token: str, post_id: str, content: str):
        # Strip spaces from token
        clean_token = token.replace(" ", "")
        
        if ":" in clean_token:
            encoded_auth = base64.b64encode(clean_token.encode("utf-8")).decode("utf-8")
            headers = {
                "Authorization": f"Basic {encoded_auth}",
                "Content-Type": "application/json",
            }
        else:
            headers = {
                "Authorization": f"Bearer {clean_token}",
                "Content-Type": "application/json",
            }
        
        update_url = f"{api_url.rstrip('/')}/{post_id}"
        payload = {"content": content}
        
        try:
            r = requests.post(update_url, headers=headers, json=payload, timeout=20)
            if r.status_code == 200:
                logger.info(f"Successfully updated WordPress post {post_id}.")
            else:
                logger.error(f"Failed to update post {post_id}: {r.status_code} - {r.text[:200]}")
        except Exception as e:
            logger.error(f"Exception updating post {post_id}: {e}")

if __name__ == "__main__":
    healer = AutoHealSystem()
    healer.run_full_audit_and_heal()
