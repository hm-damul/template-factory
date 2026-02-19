# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import requests
import subprocess
from pathlib import Path
from datetime import datetime, timezone

# Root Path
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.append(str(PROJECT_ROOT))

from promotion_dispatcher import load_channel_config
from src.ledger_manager import LedgerManager
from src.config import Config

def get_wp_comments(api_url, token):
    """WordPress 최근 댓글 가져오기"""
    # wp_api_url이 '.../wp/v2/posts' 형태일 것이므로, 'comments'로 변경
    base_url = api_url.split('/wp/v2/')[0] + '/wp/v2/comments'
    
    headers = {}
    if ":" in token:
        import base64
        encoded_auth = base64.b64encode(token.encode("utf-8")).decode("utf-8")
        headers["Authorization"] = f"Basic {encoded_auth}"
    else:
        headers["Authorization"] = f"Bearer {token}"
    
    try:
        # 최근 20개 댓글 조회
        r = requests.get(base_url, headers=headers, params={"per_page": 20, "status": "approve"}, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"Error fetching WP comments: {e}")
    return []

def extract_product_id_from_post(api_url, token, post_id):
    """포스트 정보를 통해 product_id 추출"""
    base_url = api_url.split('/wp/v2/')[0] + f'/wp/v2/posts/{post_id}'
    headers = {}
    if ":" in token:
        import base64
        encoded_auth = base64.b64encode(token.encode("utf-8")).decode("utf-8")
        headers["Authorization"] = f"Basic {encoded_auth}"
    else:
        headers["Authorization"] = f"Bearer {token}"
        
    try:
        r = requests.get(base_url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            content = data.get("content", {}).get("rendered", "")
            # 보통 URL이나 data-product-id 속성에 포함됨
            import re
            match = re.search(r'data-product-id=["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)
            
            # 본문 내 /checkout/ID 또는 /api/pay/start?product_id=ID 등 검색
            match = re.search(r'product_id=([a-zA-Z0-9\-_]+)', content)
            if match:
                return match.group(1)
            
            # 제목이나 슬러그에서 추측 가능성도 있음 (ID가 포함된 경우)
            slug = data.get("slug", "")
            # ID 패턴: 20260214-130903-topic
            match = re.search(r'(\d{8}-\d{6}-[a-zA-Z0-9\-]+)', slug)
            if match:
                return match.group(1)
                
    except Exception as e:
        print(f"Error fetching WP post {post_id}: {e}")
    return None

def trigger_recreation(product_id):
    """제품 재생성 실행"""
    print(f"Triggering recreation for product: {product_id}")
    # topic을 알아야 하므로 product_id에서 추출 시도
    # ID 형식: YYYYMMDD-HHMMSS-topic
    parts = product_id.split('-', 2)
    topic = parts[2] if len(parts) > 2 else "requested_product"
    
    cmd = [sys.executable, "auto_pilot.py", "--batch", "1", "--topic", topic, "--deploy", "1"]
    # 특정 ID를 유지하면서 재생성하는 기능은 auto_pilot에 없으므로, 
    # 여기서는 단순히 해당 주제로 새 제품을 만들거나, 
    # 기존 폴더가 비어있으면 채우는 로직이 필요함.
    # 사용자 요청의 핵심은 "결제창이 열리게" 하는 것이므로, 
    # 재생성된 제품이 ledger에 등록되면 결제 서버가 404 대신 정상 응답을 하게 됨.
    
    try:
        subprocess.run(cmd, check=True)
        print(f"Recreation triggered successfully for {product_id}")
        return True
    except Exception as e:
        print(f"Failed to trigger recreation: {e}")
    return False

def run_watcher():
    print("WordPress Comment Watcher started...")
    cfg = load_channel_config()
    blog_cfg = cfg.get("blog", {})
    wp_api_url = blog_cfg.get("wp_api_url")
    wp_token = blog_cfg.get("wp_token")
    
    if not wp_api_url or not wp_token:
        print("WordPress API config missing. Exiting.")
        return

    # 이미 처리한 댓글 ID 저장
    processed_comments_file = PROJECT_ROOT / "data" / "processed_comments.json"
    processed_ids = set()
    if processed_comments_file.exists():
        try:
            processed_ids = set(json.loads(processed_comments_file.read_text()))
        except:
            pass

    lm = LedgerManager()

    while True:
        comments = get_wp_comments(wp_api_url, wp_token)
        new_processed = False
        
        for c in comments:
            c_id = c.get("id")
            if c_id in processed_ids:
                continue
            
            content = c.get("content", {}).get("rendered", "").lower()
            # 요청 키워드 확인
            keywords = ["request", "recreate", "buy", "purchase", "결제", "구매", "요청", "살게요", "재생성"]
            if any(k in content for k in keywords):
                post_id = c.get("post")
                print(f"New request found in comment {c_id} on post {post_id}")
                
                product_id = extract_product_id_from_post(wp_api_url, wp_token, post_id)
                if product_id:
                    # 레저에 있는지 확인
                    prod = lm.get_product(product_id)
                    if not prod:
                        print(f"Product {product_id} is missing from ledger. Recreating...")
                        trigger_recreation(product_id)
                    else:
                        print(f"Product {product_id} already exists in ledger.")
                else:
                    print(f"Could not extract product_id from post {post_id}")
            
            processed_ids.add(c_id)
            new_processed = True
            
        if new_processed:
            processed_comments_file.write_text(json.dumps(list(processed_ids)))
            
        time.sleep(60) # 1분마다 확인

if __name__ == "__main__":
    run_watcher()
