# -*- coding: utf-8 -*-
"""
audit_bot.py

자율 자동 판매 시스템의 상태를 상시 검수하는 봇입니다.
1. 상품 전시 상태 검수: Vercel 배포 URL 유효성, 결제 위젯 삽입 여부 등
2. 홍보물 발행 상태 검수: 워드프레스 포스팅 유효성, 채널별 발행 결과 등
3. 자동 복구 연동: 문제가 발견된 상품은 상태를 업데이트하거나 재배포 대기열에 추가
"""

import json
import sys
from pathlib import Path

# Add project root to sys.path if run directly
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.append(str(project_root))

import logging
import requests
import time
import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from src.ledger_manager import LedgerManager
from src.config import Config
from src.promotion_validator import PromotionValidator

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AuditBot")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
DATA_DIR = PROJECT_ROOT / "data"
REPORT_PATH = DATA_DIR / "audit_report.json"

class SystemAuditBot:
    def __init__(self, db_url: str = Config.DATABASE_URL):
        self.ledger = LedgerManager(db_url)
        self.results = {
            "last_audit": None,
            "summary": {
                "total_products": 0,
                "healthy_products": 0,
                "broken_products": 0,
                "total_promotions": 0,
                "healthy_promotions": 0,
                "broken_promotions": 0
            },
            "details": []
        }

    def _validate_deployment_url(self, url: str) -> Tuple[bool, Optional[str]]:
        """URL 접속 및 콘텐츠 유효성 검사 (200 OK & No Directory Listing)"""
        if not url:
            return False, "Empty URL"
        try:
            # 타임아웃 10초
            r = requests.get(url, timeout=10)
            if r.status_code != 200:
                return False, f"Status Code {r.status_code}"
            
            # Check for Directory Listing (Vercel specific)
            if "<title>Index of /</title>" in r.text or "<h1>Index of /</h1>" in r.text:
                return False, "Directory Listing detected (Missing index.html deployment)"
            
            return True, None
        except Exception as e:
            return False, str(e)

    def _check_seo_visibility(self, title: str, url: str) -> List[str]:
        """웹 검색을 통해 상품 가시성 및 SEO 상태 확인"""
        issues = []
        if not title or len(title) < 5:
            return []
            
        try:
            from src.ai_web_researcher import web_researcher
            # Search for the exact title
            # Note: This is a slow operation, so we might want to cache or rate limit in production
            res = web_researcher.check_visibility(title, url)
            if not res['visible']:
                issues.append(f"SEO Warning: Not visible in top 20 for title '{title}'")
        except Exception as e:
            logger.warning(f"SEO check skipped: {e}")
        return issues

    def audit_products(self) -> List[Dict[str, Any]]:
        """원장에 등록된 모든 상품의 전시 상태를 검수합니다."""
        products = self.ledger.list_products(limit=1000)
        self.results["summary"]["total_products"] = len(products)
        
        product_audits = []
        for prod in products:
            pid = prod.get("id")
            status = prod.get("status")
            
            if status == "DELETED":
                continue

            meta = prod.get("metadata") or {}
            deployment_url = meta.get("deployment_url")
            title = meta.get("title") or pid
            
            audit_item = {
                "product_id": pid,
                "type": "product",
                "status": status,
                "issues": []
            }
            
            # 1. PUBLISHED 상태 상품의 URL 체크
            if status == "PUBLISHED":
                if not deployment_url:
                    audit_item["issues"].append("Missing deployment_url in metadata")
                else:
                    is_ok, error_msg = self._validate_deployment_url(deployment_url)
                    if not is_ok:
                        audit_item["issues"].append(f"Deployment URL dead/invalid: {error_msg}")
                    else:
                        # [Live Content Check] Payment Widget
                        try:
                            r = requests.get(deployment_url, timeout=5)
                            content = r.text
                            if "startPay" not in content and "choose-plan" not in content and "crypto-payment-widget" not in content:
                                audit_item["issues"].append("Live site missing payment widget/script")
                        except:
                            pass

                        # [AI Web Integration] SEO Visibility Check
                        # Only check if URL is alive
                        seo_issues = self._check_seo_visibility(title, deployment_url)
                        audit_item["issues"].extend(seo_issues)
            
            # 2. 로컬 파일 존재 여부 체크
            p_dir = OUTPUTS_DIR / pid
            if not (p_dir / "index.html").exists():
                audit_item["issues"].append("Missing index.html in outputs")
            
            # 3. 결제 위젯 삽입 여부 체크 (index.html 내용 확인)
            if (p_dir / "index.html").exists():
                content = (p_dir / "index.html").read_text(encoding="utf-8", errors="ignore")
                if "startPay" not in content and "choose-plan" not in content and "crypto-payment-widget" not in content:
                    audit_item["issues"].append("Payment widget not found in index.html")

            # 4. 홍보 콘텐츠 품질 검수 (로컬 파일)
            promo_dir = p_dir / "promotions"
            content_path = promo_dir / "blog_longform.md"
            if not content_path.exists():
                content_path = promo_dir / "blog_post.md"
            
            if content_path.exists():
                try:
                    p_content = content_path.read_text(encoding="utf-8", errors="ignore")
                    lines = p_content.splitlines()
                    p_title = lines[0].replace("#", "").strip() if lines else "Untitled"
                    
                    pv_result = PromotionValidator.validate_blog_post(p_content, p_title)
                    if not pv_result.passed:
                        audit_item["issues"].append(f"Promotion quality failed (Score {pv_result.score}): Missing {', '.join(pv_result.schema_errors)}")
                except Exception as e:
                    logger.warning(f"Promotion validation error for {pid}: {e}")

            if not audit_item["issues"]:
                self.results["summary"]["healthy_products"] += 1
            else:
                self.results["summary"]["broken_products"] += 1
                logger.error(f"Product {pid} audit failed: {audit_item['issues']}")
            
            product_audits.append(audit_item)
            
        return product_audits

    def _check_wp_post_status(self, wp_api_url: str, wp_token: str, post_id: str, expected_url: str = None) -> Tuple[bool, List[str]]:
        """WordPress REST API를 통해 포스트 상태를 상세 검수합니다."""
        issues = []
        try:
            # API URL에서 개별 포스트 엔드포인트 구성
            # wp_api_url은 보통 .../wp-json/wp/v2/posts 형태임
            check_url = f"{wp_api_url.rstrip('/')}/{post_id}"
            
            headers = {"Content-Type": "application/json"}
            if wp_token:
                if ":" in wp_token:
                    import base64
                    encoded_auth = base64.b64encode(wp_token.encode("utf-8")).decode("utf-8")
                    headers["Authorization"] = f"Basic {encoded_auth}"
                else:
                    headers["Authorization"] = f"Bearer {wp_token}"
            
            r = requests.get(check_url, headers=headers, timeout=10)
            if r.status_code != 200:
                issues.append(f"WordPress API returned {r.status_code} for post {post_id}")
                return False, issues
            
            data = r.json()
            if data.get("status") != "publish":
                issues.append(f"WordPress post status is '{data.get('status')}', not 'publish'")
            
            # 본문에 결제 링크나 대시보드 URL이 포함되어 있는지 추가 검증 가능
            content = data.get("content", {}).get("rendered", "")
            
            # Check links in content
            links = re.findall(r'href=[\'"](https?://[^\'"]+)[\'"]', content)
            product_link_found = False
            
            for link in links:
                # If we have a specific expected URL, check for it
                if expected_url and expected_url in link:
                    product_link_found = True
                # Otherwise fall back to generic checks
                elif not expected_url and ("vercel.app" in link or "best-pick-global" in link):
                    product_link_found = True
                
                # Check if the product link is alive (only if it looks like a product link)
                if expected_url and expected_url in link:
                     try:
                        r_link = requests.head(link, timeout=5, allow_redirects=True)
                        if r_link.status_code >= 400:
                            issues.append(f"Broken product link in post: {link} ({r_link.status_code})")
                     except:
                        issues.append(f"Unreachable product link in post: {link}")
            
            if not product_link_found:
                if expected_url:
                    issues.append(f"No link to {expected_url} found in post content")
                else:
                    issues.append("No product link found in post content")

            # [AI Web Integration] Check SEO Visibility of the Blog Post
            link = data.get("link")
            title = data.get("title", {}).get("rendered", "")
            if link and title:
                # Remove HTML tags from title if any
                clean_title = re.sub('<[^<]+?>', '', title)
                seo_issues = self._check_seo_visibility(clean_title, link)
                issues.extend(seo_issues)
                
            return len(issues) == 0, issues
        except Exception as e:
            issues.append(f"WordPress API check failed: {str(e)}")
            return False, issues

    def audit_promotions(self) -> List[Dict[str, Any]]:
        """상품별 홍보물 발행 상태를 검수합니다."""
        products = self.ledger.list_products(limit=1000)
        promo_audits = []
        
        # 워드프레스 설정 로드
        wp_api_url = ""
        wp_token = ""
        try:
            import sys
            from pathlib import Path
            root = Path(__file__).resolve().parent.parent
            if str(root) not in sys.path:
                sys.path.append(str(root))
            from promotion_dispatcher import load_channel_config
            cfg = load_channel_config()
            blog_cfg = cfg.get("blog", {})
            wp_api_url = blog_cfg.get("wp_api_url", "")
            wp_token = blog_cfg.get("wp_token", "")
        except Exception as e:
            logger.warning(f"설정 로드 중 오류: {e}")
            # 설정 로드 실패 시에도 계속 진행 (기본값 사용)

        for prod in products:
            pid = prod.get("id")
            if prod.get("status") == "DELETED":
                continue
            meta = prod.get("metadata") or {}
            wp_post_id = meta.get("wp_post_id")
            
            # WordPress 발행 여부 확인
            if wp_post_id:
                self.results["summary"]["total_promotions"] += 1
                audit_item = {
                    "product_id": pid,
                    "type": "promotion_wordpress",
                    "post_id": wp_post_id,
                    "issues": []
                }
                
                deployment_url = meta.get("deployment_url")

                if wp_api_url:
                    ok, wp_issues = self._check_wp_post_status(wp_api_url, wp_token, wp_post_id, expected_url=deployment_url)
                    if not ok:
                        audit_item["issues"].extend(wp_issues)
                else:
                    audit_item["issues"].append("WordPress config missing for verification")

                if not audit_item["issues"]:
                    self.results["summary"]["healthy_promotions"] += 1
                else:
                    self.results["summary"]["broken_promotions"] += 1
                
                promo_audits.append(audit_item)
            
            # 기타 채널 발행 결과 체크 (publish_results.json)
            results_path = OUTPUTS_DIR / pid / "promotions" / "publish_results.json"
            if results_path.exists():
                try:
                    res = json.loads(results_path.read_text(encoding="utf-8"))
                    
                    # Handle new structure with "sent" list
                    if "sent" in res and isinstance(res["sent"], list):
                        for item in res["sent"]:
                            channel = item.get("channel")
                            if not channel or channel == "blog_wordpress": continue
                            
                            self.results["summary"]["total_promotions"] += 1
                            audit_item = {
                                "product_id": pid,
                                "type": f"promotion_{channel}",
                                "issues": []
                            }
                            if not item.get("ok"):
                                audit_item["issues"].append(f"Channel {channel} publish failed: {item.get('msg') or item.get('note') or 'unknown error'}")
                            
                            if not audit_item["issues"]:
                                self.results["summary"]["healthy_promotions"] += 1
                            else:
                                self.results["summary"]["broken_promotions"] += 1
                            promo_audits.append(audit_item)
                            
                    # Handle old structure (dict of channel->info)
                    else:
                        for channel, info in res.items():
                            if channel in ["product_id", "created_at", "dry_run", "sent"]: continue
                            if channel == "wordpress": continue 
                            
                            if not isinstance(info, dict): continue
                            
                            self.results["summary"]["total_promotions"] += 1
                            audit_item = {
                                "product_id": pid,
                                "type": f"promotion_{channel}",
                                "issues": []
                            }
                            if not info.get("ok"):
                                audit_item["issues"].append(f"Channel {channel} publish failed: {info.get('error')}")
                            
                            if not audit_item["issues"]:
                                self.results["summary"]["healthy_promotions"] += 1
                            else:
                                self.results["summary"]["broken_promotions"] += 1
                            promo_audits.append(audit_item)
                except Exception as e:
                    logger.warning(f"Error parsing publish_results.json for {pid}: {e}")
                    pass
                    
        return promo_audits

    def _check_payment_server(self) -> List[str]:
        """결제 서버 상태 및 엔드포인트 메서드(GET/POST) 지원 여부 검수"""
        issues = []
        payment_port = os.getenv("PAYMENT_PORT", "5000")
        base_url = os.getenv("PAYMENT_SERVER_URL", f"http://127.0.0.1:{payment_port}")
        
        # 1. Health check
        try:
            r = requests.get(f"{base_url}/health", timeout=5)
            if r.status_code != 200:
                issues.append(f"Payment server health check failed: {r.status_code}")
        except Exception as e:
            issues.append(f"Payment server unreachable: {e}")
            return issues # 서버가 죽었으면 더 이상 검사 불가

        # 2. Check 405 on /api/pay/start (simulate GET request)
        # GET 요청이 허용되어야 함 (최근 수정사항 반영)
        try:
            # Pick a valid product ID if available
            test_pid = "crypto-template-001"
            products = self.ledger.list_products(limit=1)
            if products:
                test_pid = products[0]["id"]

            # GET request with parameters to simulate real usage
            r = requests.get(f"{base_url}/api/pay/start?product_id={test_pid}&price_amount=19.9", timeout=5)
            
            if r.status_code == 405:
                issues.append("Payment endpoint /api/pay/start returns 405 for GET (should be allowed)")
            elif r.status_code not in [200, 400, 404]:
                # 404 is allowed if product not found (even if we picked one, maybe server db is out of sync)
                issues.append(f"Payment endpoint /api/pay/start unexpected status: {r.status_code}")
        except Exception as e:
            issues.append(f"Payment endpoint check failed: {e}")

        return issues

    def run_full_audit(self):
        """전체 검수를 실행하고 결과를 저장합니다."""
        logger.info("Starting full system audit...")
        self.results["last_audit"] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # 시스템 서버 검수
        payment_issues = self._check_payment_server()
        if payment_issues:
            self.results["details"].append({
                "type": "system_payment_server",
                "status": "ERROR",
                "issues": payment_issues
            })
            logger.error(f"Payment server audit failed: {payment_issues}")

        # 상품 검수
        product_results = self.audit_products()
        # 홍보물 검수
        promo_results = self.audit_promotions()
        
        self.results["details"] = product_results + promo_results
        
        # 결과 저장
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
            
        logger.info(f"Audit completed. Healthy: {self.results['summary']['healthy_products']}/{self.results['summary']['total_products']} products.")
        
        # 자동 복구 트리거 (Broken 상품들 상태 변경)
        self._trigger_auto_healing(product_results)
        
        return self.results

    def _trigger_auto_healing(self, product_results: List[Dict[str, Any]]):
        """문제가 발견된 상품들을 'WAITING_FOR_DEPLOYMENT'로 되돌려 재배포 유도"""
        for item in product_results:
            if item["issues"] and item["status"] == "PUBLISHED":
                pid = item["product_id"]
                logger.info(f"Triggering auto-healing for product: {pid}")
                try:
                    # 상태를 WAITING_FOR_DEPLOYMENT로 변경하여 auto_mode_daemon이 재배포하도록 함
                    self.ledger.update_product(pid, status="WAITING_FOR_DEPLOYMENT")
                except Exception as e:
                    logger.error(f"Failed to update status for healing: {pid} - {str(e)}")

if __name__ == "__main__":
    bot = SystemAuditBot()
    bot.run_full_audit()
