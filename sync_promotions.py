# -*- coding: utf-8 -*-
import sys
import json
import time
from pathlib import Path
from typing import List, Dict, Any

# 프로젝트 루트 설정
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT))

# 코어 모듈 임포트
from src.ledger_manager import LedgerManager
from src.config import Config
from promotion_dispatcher import dispatch_publish

def get_published_products() -> List[Dict[str, Any]]:
    """DB에서 PUBLISHED 상태인 제품 목록을 가져옵니다."""
    try:
        lm = LedgerManager(Config.DATABASE_URL)
        # get_products_by_status가 src/ledger_manager.py 하단에 정의되어 있다고 가정
        # (auto_mode_daemon.py에서 사용 중인 것을 확인)
        return lm.get_products_by_status("PUBLISHED")
    except Exception as e:
        print(f"Error fetching products from DB: {e}")
        return []

def check_already_promoted(product_id: str) -> bool:
    """제품의 홍보 발행 결과 파일이 존재하는지 확인합니다."""
    # dispatch_publish가 성공하면 outputs/<pid>/promotions/publish_results.json 을 생성함
    result_path = PROJECT_ROOT / "outputs" / product_id / "promotions" / "publish_results.json"
    if not result_path.exists():
        return False
    
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
        sent = data.get("sent", [])
        # 워드프레스(blog_wordpress)가 성공했는지 확인
        for s in sent:
            if s.get("channel") == "blog_wordpress" and s.get("ok"):
                return True
    except Exception:
        pass
    
    return False

def sync_promotions():
    """모든 PUBLISHED 제품에 대해 미발행된 홍보글을 발행합니다."""
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Promotion Sync Start...")
    
    products = get_published_products()
    if not products:
        print("No PUBLISHED products found in database.")
        return

    print(f"Found {len(products)} PUBLISHED products.")
    
    count_success = 0
    count_skipped = 0
    count_failed = 0

    for p in products:
        pid = p["id"]
        if check_already_promoted(pid):
            # print(f"Skipping {pid} (Already promoted)")
            count_skipped += 1
            continue
        
        print(f"Dispatching promotion for: {pid}")
        try:
            # dispatch_publish는 promotion_dispatcher.py에 정의됨
            # 내부적으로 build_channel_payloads를 호출하여 마케팅 문구를 생성하고,
            # promo_channels.json 설정에 따라 워드프레스 등에 발행함.
            res = dispatch_publish(pid)
            
            # 결과 확인
            sent = res.get("sent", [])
            wp_ok = any(s.get("channel") == "blog_wordpress" and s.get("ok") for s in sent)
            
            if wp_ok:
                print(f"Successfully promoted {pid} to WordPress.")
                count_success += 1
            else:
                msg = next((s.get("msg") for s in sent if s.get("channel") == "blog_wordpress"), "Unknown error")
                print(f"Failed to promote {pid} to WordPress: {msg}")
                count_failed += 1
                
            # API 레이트 리밋 등을 고려하여 짧은 대기
            time.sleep(2)
            
        except Exception as e:
            print(f"Error dispatching {pid}: {e}")
            count_failed += 1

    print(f"--- Sync Result ---")
    print(f"Total: {len(products)}")
    print(f"Success: {count_success}")
    print(f"Skipped: {count_skipped} (Already exists)")
    print(f"Failed: {count_failed}")
    print(f"-------------------")

if __name__ == "__main__":
    sync_promotions()
