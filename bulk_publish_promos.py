# -*- coding: utf-8 -*-
import sys
from pathlib import Path
import json
import logging
import time

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT))

from promotion_dispatcher import dispatch_publish

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def bulk_publish(limit=50):
    outputs_dir = PROJECT_ROOT / "outputs"
    if not outputs_dir.exists():
        logger.error("outputs directory not found.")
        return

    # promotions/channel_payloads.json이 있는 디렉토리들 찾기
    product_dirs = []
    for d in outputs_dir.iterdir():
        if d.is_dir() and (d / "promotions" / "channel_payloads.json").exists():
            # 이미 성공적으로 발행된 경우 건너뛰기
            results_path = d / "promotions" / "publish_results.json"
            if results_path.exists():
                try:
                    res_data = json.loads(results_path.read_text(encoding="utf-8"))
                    sent_list = res_data.get("sent", [])
                    wp_ok = any(s.get("channel") == "blog_wordpress" and s.get("ok") for s in sent_list)
                    if wp_ok:
                        continue
                except:
                    pass
            product_dirs.append(d)
    
    logger.info(f"Found {len(product_dirs)} products with ready payloads.")
    
    # 최근 수정된 순서대로 정렬 (최근 재생성한 것부터)
    product_dirs.sort(key=lambda x: (x / "promotions" / "channel_payloads.json").stat().st_mtime, reverse=True)

    success_count = 0
    fail_count = 0
    
    # 너무 많이 한꺼번에 올리면 서버 부하가 있을 수 있으니 limit 설정
    to_publish = product_dirs[:limit]
    logger.info(f"Attempting to publish {len(to_publish)} products (limit={limit}).")

    for p_dir in to_publish:
        product_id = p_dir.name
        try:
            logger.info(f"[{product_id}] Publishing promotions...")
            results = dispatch_publish(product_id)
            
            # 결과 확인
            sent_list = results.get("sent", [])
            all_ok = all(s.get("ok") for s in sent_list if s.get("channel") != "blog") # blog는 필수
            
            # WordPress 결과 상세 확인
            wp_res = next((s for s in sent_list if s.get("channel") == "blog_wordpress"), None)
            if wp_res and wp_res.get("ok"):
                logger.info(f"[{product_id}] Successfully published to WordPress.")
                success_count += 1
            else:
                msg = wp_res.get("msg") if wp_res else "No WP config"
                logger.warning(f"[{product_id}] Failed or skipped WordPress: {msg}")
                fail_count += 1
            
            # 서버 부하 방지를 위한 짧은 대기
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"[{product_id}] Critical error during publish: {e}")
            fail_count += 1

    logger.info(f"Bulk publish finished. Success: {success_count}, Fail/Skip: {fail_count}")

if __name__ == "__main__":
    # 인자가 있으면 limit으로 사용
    limit = 50
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except:
            pass
    bulk_publish(limit=limit)
