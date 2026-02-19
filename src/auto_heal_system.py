
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
import promotion_dispatcher

# Try to import deploy_static_files from root module
try:
    import sys
    sys.path.append(str(Path(__file__).parent.parent))
    from deploy_module_vercel_api import deploy_static_files
except ImportError:
    # Fallback or error logging
    deploy_static_files = None

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

class VercelAPIDeployerWrapper:
    def __init__(self):
        self.vercel_api_token = Config.VERCEL_API_TOKEN
        self.vercel_team_id = os.getenv("VERCEL_TEAM_ID") or os.getenv("VERCEL_ORG_ID")

    def _vercel_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.vercel_api_token}",
            "Content-Type": "application/json",
        }

    def _vercel_team_qs(self) -> str:
        if self.vercel_team_id:
            return f"?teamId={self.vercel_team_id}"
        return ""

    def _disable_vercel_sso(self, project_name: str):
        """Disable Vercel SSO Protection for public access."""
        qs = self._vercel_team_qs()
        url = f"https://api.vercel.com/v9/projects/{project_name}{qs}"
        payloads = [{"ssoProtection": None}, {"directoryListing": True}]
        for payload in payloads:
            try:
                requests.patch(url, headers=self._vercel_headers(), json=payload)
            except Exception as e:
                logger.warning(f"Failed to update project settings for {project_name}: {e}")

    def _set_vercel_env_vars(self, project_name: str):
        """Set necessary environment variables for the Vercel project."""
        env_vars = {
            "NOWPAYMENTS_API_KEY": os.getenv("NOWPAYMENTS_API_KEY"),
            "PAYMENT_MODE": os.getenv("PAYMENT_MODE", "nowpayments"),
            "MERCHANT_WALLET_ADDRESS": os.getenv("MERCHANT_WALLET_ADDRESS"),
            "CHAIN_ID": os.getenv("CHAIN_ID", "1"),
            "UPSTASH_REDIS_REST_URL": os.getenv("UPSTASH_REDIS_REST_URL"),
            "UPSTASH_REDIS_REST_TOKEN": os.getenv("UPSTASH_REDIS_REST_TOKEN"),
            "DOWNLOAD_TOKEN_SECRET": os.getenv("DOWNLOAD_TOKEN_SECRET")
        }
        qs = self._vercel_team_qs()
        url = f"https://api.vercel.com/v9/projects/{project_name}/env{qs}"
        
        # Check existing envs to update or create
        try:
            r = requests.get(url, headers=self._vercel_headers())
            existing_envs = {}
            if r.status_code == 200:
                for e in r.json().get("envs", []):
                    existing_envs[e['key']] = {'id': e['id'], 'value': e.get('value')}
            
            for key, value in env_vars.items():
                if not value: continue
                
                if key in existing_envs:
                    # Update (Patch)
                    env_id = existing_envs[key]['id']
                    patch_url = f"https://api.vercel.com/v9/projects/{project_name}/env/{env_id}{qs}"
                    payload = {"value": value, "target": ["production", "preview", "development"]}
                    requests.patch(patch_url, headers=self._vercel_headers(), json=payload)
                else:
                    # Create (Post)
                    payload = {
                        "key": key, "value": value, "type": "encrypted",
                        "target": ["production", "preview", "development"]
                    }
                    requests.post(url, headers=self._vercel_headers(), json=payload)
        except Exception as e:
            logger.error(f"Failed to set env vars for {project_name}: {e}")

    def deploy(self, directory: str, project_name: str) -> str:
        if not deploy_static_files:
            logger.error("deploy_static_files function not available.")
            return ""
            
        # Read all files in directory
        files = []
        dir_path = Path(directory)
        for f in dir_path.rglob("*"):
            if f.is_file():
                try:
                    rel_path = f.relative_to(dir_path).as_posix()
                    content = f.read_bytes()
                    files.append((rel_path, content))
                except Exception as e:
                    logger.warning(f"Failed to read file {f}: {e}")
        
        # [CRITICAL FIX] Add vercel.json and api/ files for full functionality
        project_root = Path(__file__).resolve().parents[1]
        
        # 1. vercel.json
        vercel_json = project_root / "vercel.json"
        if vercel_json.exists():
            files.append(("vercel.json", vercel_json.read_bytes()))
            
        # 2. api/ folder
        api_dir = project_root / "api"
        if api_dir.exists():
            for p in api_dir.rglob("*"):
                if p.is_file() and "__pycache__" not in str(p):
                    rel = p.relative_to(project_root).as_posix()
                    files.append((rel, p.read_bytes()))
                    
        # 3. secrets.json
        secrets_json = project_root / "data" / "secrets.json"
        if secrets_json.exists():
            files.append(("data/secrets.json", secrets_json.read_bytes()))

        # 4. [CRITICAL] Required root modules for API functionality
        required_modules = [
            "payment_api.py",
            "nowpayments_client.py",
            "order_store.py",
            "evm_verifier.py",
        ]
        for mod in required_modules:
            mod_path = project_root / mod
            if mod_path.exists():
                files.append((mod, mod_path.read_bytes()))

        if not files:
            logger.error(f"No files found in {directory}")
            return ""
            
        try:
            url = deploy_static_files(project_name, files, production=True)
            if url:
                # Post-deployment configuration
                self._set_vercel_env_vars(project_name)
                self._disable_vercel_sso(project_name)
            return url
        except Exception as e:
            logger.error(f"Vercel deployment failed: {e}")
            return ""

class AutoHealSystem:
    def __init__(self):
        self.audit_bot = SystemAuditBot()
        self.ledger = LedgerManager(Config.DATABASE_URL)
        self.deployer = VercelAPIDeployerWrapper()
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
            if any("Deployment URL dead" in i or "Missing deployment_url" in i for i in issues):
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
            # Use Vercel API Deployer
            # We need a project name. Let's try to get it from metadata or generate one.
            prod = self.ledger.get_product(product_id)
            meta = prod.get("metadata", {}) if prod else {}
            if isinstance(meta, str):
                meta = json.loads(meta)
            
            project_name = meta.get("vercel_project_name")
            if not project_name:
                # Fallback to a name based on title or ID
                title = meta.get("title") or prod.get("topic") or "product"
                import re
                safe_title = re.sub(r'[^a-zA-Z0-9-]', '', title.replace(' ', '-').lower())
                project_name = f"{safe_title[:30]}-{int(time.time())}"
            
            logger.info(f"Deploying to Vercel project: {project_name}")
            deployment_url = self.deployer.deploy(str(product_dir), project_name)
            
            if deployment_url:
                logger.info(f"Redeployment successful: {deployment_url}")
                
                # Payment Flow Verification
                logger.info(f"Verifying payment flow for {product_id}...")
                verifier = PaymentFlowVerifier()
                # Get price from metadata or default
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
                    "vercel_project_name": project_name,
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
        if ":" in token:
            encoded_auth = base64.b64encode(token.encode("utf-8")).decode("utf-8")
            headers = {
                "Authorization": f"Basic {encoded_auth}",
                "Content-Type": "application/json",
            }
        else:
            headers = {
                "Authorization": f"Bearer {token}",
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
