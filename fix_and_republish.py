# -*- coding: utf-8 -*-
import sys
from pathlib import Path
import json
import logging

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT))

from src.ledger_manager import LedgerManager
from promotion_factory import generate_promotions
from promotion_dispatcher import dispatch_publish

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_and_republish(product_id: str):
    db_url = f"sqlite:///{PROJECT_ROOT}/data/ledger.db"
    ledger = LedgerManager(db_url)
    
    product_dir = PROJECT_ROOT / "outputs" / product_id
    if not product_dir.exists():
        logger.error(f"Product directory not found: {product_id}")
        return

    manifest_path = product_dir / "manifest.json"
    schema_path = product_dir / "product_schema.json"
    
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    elif schema_path.exists():
        logger.info(f"[{product_id}] manifest.json 누락. product_schema.json에서 복구 시도.")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        manifest = {
            "id": product_id,
            "title": schema.get("title", "Digital Asset"),
            "topic": schema.get("sections", {}).get("hero", {}).get("subheadline", "Crypto Automation"),
            "metadata": {
                "final_price_usd": 49.0
            }
        }
    else:
        logger.error(f"manifest.json and product_schema.json not found for {product_id}")
        return

    title = manifest.get("title", "Digital Asset")
    topic = manifest.get("topic", "Crypto Automation")
    price_usd = manifest.get("metadata", {}).get("final_price_usd", 49.0)
    
    # 1. 갱신된 로직으로 홍보 자산 재생성
    logger.info(f"[{product_id}] 홍보 자산 재생성 중...")
    generate_promotions(product_dir, product_id, title, topic, price_usd)
    
    # 2. 배포 URL이 ledger에 있는지 확인하고 manifest.json 업데이트
    product_info = ledger.get_product(product_id)
    deployment_url = product_info.get("metadata", {}).get("deployment_url") or product_info.get("metadata", {}).get("vercel_url")
    
    if deployment_url:
        logger.info(f"[{product_id}] 원장에서 배포 URL 발견: {deployment_url}. manifest.json 업데이트.")
        if "metadata" not in manifest:
            manifest["metadata"] = {}
        manifest["metadata"]["deployment_url"] = deployment_url
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        logger.warning(f"[{product_id}] 배포 URL을 찾을 수 없습니다.")
    
    # 3. 홍보 채널(워드프레스 등)에 다시 발행
    logger.info(f"[{product_id}] 홍보 채널 재발행 중...")
    # promotion_dispatcher.py의 dispatch_publish는 내부적으로 build_channel_payloads를 호출함
    results = dispatch_publish(product_id)
    logger.info(f"[{product_id}] 재발행 결과: {results}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_id = sys.argv[1]
        fix_and_republish(target_id)
    else:
        # 스크린샷에 나온 제품 ID 기본값
        fix_and_republish("20260214-130903-ai-trading-bot")
