# -*- coding: utf-8 -*-
import requests
import json
import base64
from pathlib import Path
import logging

# 프로젝트 루트 및 설정 로드
PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_ROOT / "data" / "promo_channels.json"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def delete_all_wp_posts():
    if not CONFIG_PATH.exists():
        logger.error("Config file not found.")
        return

    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        blog_cfg = cfg.get("blog", {})
        wp_api_url = blog_cfg.get("wp_api_url")
        wp_token = blog_cfg.get("wp_token")
        
        if not wp_api_url or not wp_token:
            logger.error("WordPress API URL or Token missing in config.")
            return

        # Auth Header
        if ":" in wp_token:
            encoded_auth = base64.b64encode(wp_token.encode("utf-8")).decode("utf-8")
            headers = {"Authorization": f"Basic {encoded_auth}"}
        else:
            headers = {"Authorization": f"Bearer {wp_token}"}

        # 모든 포스트 가져오기 (기본적으로 10개씩 가져오므로 여러 번 시도 필요할 수 있음)
        # 여기서는 최대 100개씩 삭제 시도
        params = {"per_page": 100, "status": "publish,draft,pending,private,future"}
        
        while True:
            response = requests.get(wp_api_url, headers=headers, params=params, timeout=20)
            if response.status_code != 200:
                logger.error(f"Failed to fetch posts: {response.status_code} {response.text}")
                break
            
            posts = response.json()
            if not posts:
                logger.info("No more posts to delete.")
                break
            
            logger.info(f"Found {len(posts)} posts. Starting deletion...")
            
            for post in posts:
                post_id = post['id']
                # force=true를 주면 휴지통을 거치지 않고 영구 삭제
                delete_url = f"{wp_api_url}/{post_id}"
                del_res = requests.delete(delete_url, headers=headers, params={"force": "true"}, timeout=20)
                
                if del_res.status_code == 200:
                    logger.info(f"Deleted post ID {post_id}: {post.get('title', {}).get('rendered', 'No Title')}")
                else:
                    logger.warning(f"Failed to delete post ID {post_id}: {del_res.status_code}")
            
            # 한 번 더 루프를 돌아 남은 게 있는지 확인 (페이지네이션 생략하고 계속 가져오기)
            # WP API는 삭제된 후 다음 호출 시 새로운 리스트를 줌

    except Exception as e:
        logger.error(f"An error occurred: {e}")

if __name__ == "__main__":
    delete_all_wp_posts()
