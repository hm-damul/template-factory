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
from promotion_dispatcher import build_channel_payloads

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def bulk_regenerate():
    db_url = f"sqlite:///{PROJECT_ROOT}/data/ledger.db"
    ledger = LedgerManager(db_url)
    
    # 모든 제품 가져오기 (상태 상관없이 홍보 자산은 생성 가능)
    # ledger_manager.py의 get_products_by_status 대신 직접 쿼리하거나 모든 제품 목록 가져오기
    # 여기서는 간단히 outputs 폴더를 순회
    outputs_dir = PROJECT_ROOT / "outputs"
    if not outputs_dir.exists():
        logger.error("outputs directory not found.")
        return

    product_dirs = [d for d in outputs_dir.iterdir() if d.is_dir()]
    logger.info(f"Found {len(product_dirs)} product directories.")

    success_count = 0
    for p_dir in product_dirs:
        product_id = p_dir.name
        manifest_path = p_dir / "manifest.json"
        schema_path = p_dir / "product_schema.json"
        
        # manifest.json이 없으면 product_schema.json이나 product_ko.md에서 복구 시도
        if not manifest_path.exists():
            logger.warning(f"[{product_id}] manifest.json not found. Attempting recovery.")
            
            recovered_data = {}
            
            # 1. product_schema.json 확인 (가장 선호되는 영어 소스)
            if schema_path.exists():
                try:
                    schema = json.loads(schema_path.read_text(encoding="utf-8"))
                    recovered_data["title"] = schema.get("title")
                    recovered_data["topic"] = schema.get("sections", {}).get("hero", {}).get("subheadline", "")
                    price_str = schema.get("pricing", {}).get("price", "$29").replace("$", "")
                    try:
                        recovered_data["price_usd"] = float(price_str)
                    except:
                        recovered_data["price_usd"] = 29.0
                    logger.info(f"[{product_id}] Recovered info from product_schema.json (English)")
                except Exception as e:
                    logger.error(f"[{product_id}] Error reading schema: {e}")

            # 2. product_en.md 확인 (두 번째로 선호되는 영어 소스)
            en_md_path = p_dir / "product_en.md"
            if not recovered_data.get("title") and en_md_path.exists():
                try:
                    content = en_md_path.read_text(encoding="utf-8")
                    for line in content.splitlines():
                        if line.startswith("# "):
                            recovered_data["title"] = line[2:].strip()
                        if line.startswith("**topic:**"):
                            recovered_data["topic"] = line[10:].strip()
                    logger.info(f"[{product_id}] Recovered info from product_en.md (English)")
                except Exception as e:
                    logger.error(f"[{product_id}] Error reading en_md: {e}")

            # 3. product_ko.md 확인 (마지막 수단, 하지만 템플릿은 영어로 생성됨)
            ko_md_path = p_dir / "product_ko.md"
            if not recovered_data.get("title") and ko_md_path.exists():
                try:
                    content = ko_md_path.read_text(encoding="utf-8")
                    for line in content.splitlines():
                        if line.startswith("# "):
                            recovered_data["title"] = line[2:].strip()
                        if line.startswith("**topic:**"):
                            recovered_data["topic"] = line[10:].strip()
                    logger.info(f"[{product_id}] Recovered info from product_ko.md (Fallback)")
                except Exception as e:
                    logger.error(f"[{product_id}] Error reading ko_md: {e}")

            if not recovered_data.get("title"):
                logger.error(f"[{product_id}] Could not recover basic info. Skipping.")
                continue
                
            # 복구된 데이터로 manifest.json 생성
            manifest = {
                "product_id": product_id,
                "title": recovered_data.get("title", "Digital Asset"),
                "topic": recovered_data.get("topic", "Crypto Automation"),
                "metadata": {
                    "final_price_usd": recovered_data.get("price_usd", 29.0)
                }
            }
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
            logger.info(f"[{product_id}] manifest.json recovered and saved.")

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            
            # 필요한 정보 추출
            title = manifest.get("title") or manifest.get("product", {}).get("title", "Digital Asset")
            topic = manifest.get("topic") or manifest.get("metadata", {}).get("initial_topic", "Crypto Automation")
            
            # 가격 정보
            price_usd = 29.0
            if "metadata" in manifest and "final_price_usd" in manifest["metadata"]:
                price_usd = float(manifest["metadata"]["final_price_usd"])
            
            logger.info(f"[{product_id}] Regenerating promotions for: {title}")
            
            # 1. promotion_factory를 통한 기본 자산 생성
            generate_promotions(
                product_dir=p_dir,
                product_id=product_id,
                title=title,
                topic=topic,
                price_usd=price_usd
            )
            
            # 2. promotion_dispatcher를 통한 채널별 페이로드 생성 (이미지 및 링크 포함)
            build_channel_payloads(product_id)
            
            success_count += 1
        except Exception as e:
            logger.error(f"[{product_id}] Failed to regenerate: {e}")

    logger.info(f"Successfully regenerated promotions for {success_count} products.")

if __name__ == "__main__":
    bulk_regenerate()
