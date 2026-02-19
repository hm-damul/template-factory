# -*- coding: utf-8 -*-
import json
import logging
from pathlib import Path
import sys

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT))

from promotion_factory import generate_promotions
from promotion_dispatcher import dispatch_publish

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def analyze_and_redeploy():
    outputs_dir = PROJECT_ROOT / "outputs"
    if not outputs_dir.exists():
        logger.error("outputs directory not found.")
        return

    product_dirs = [d for d in outputs_dir.iterdir() if d.is_dir()]
    logger.info(f"Analyzing {len(product_dirs)} products...")

    recreated_count = 0
    published_count = 0
    
    for p_dir in product_dirs:
        product_id = p_dir.name
        promotions_dir = p_dir / "promotions"
        blog_md_path = promotions_dir / "blog_longform.md"
        manifest_path = p_dir / "manifest.json"
        
        needs_recreate = False
        manifest_title = ""
        
        if manifest_path.exists():
            try:
                m = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest_title = m.get("title", "")
            except: pass

        # 1. 파일 존재 여부 확인
        if not blog_md_path.exists():
            logger.info(f"[{product_id}] Missing blog_longform.md. Recreating...")
            needs_recreate = True
        else:
            # 2. 내용 분석 (부실함 체크)
            content = blog_md_path.read_text(encoding="utf-8")
            
            # 품질 기준: 800자 미만, 특정 키워드(Trust, Passive Income 등) 부재, 한글 포함 여부 등
            if len(content) < 800:
                logger.info(f"[{product_id}] Content too short ({len(content)} chars). Recreating...")
                needs_recreate = True
            elif "The Ultimate Blueprint" not in content and "Trust" not in content:
                # 구버전 템플릿인 경우
                logger.info(f"[{product_id}] Old template detected. Recreating...")
                needs_recreate = True
            elif any(0xAC00 <= ord(c) <= 0xD7A3 for c in content):
                # 한글이 포함되어 있는 경우 (영어 전용 요청 위반)
                logger.info(f"[{product_id}] Korean characters detected. Recreating...")
                needs_recreate = True
            elif manifest_title and manifest_title not in content:
                # manifest의 제목이 홍보글에 반영되지 않은 경우 (최근 번역됨)
                logger.info(f"[{product_id}] Title mismatch (Manifest: {manifest_title}). Recreating...")
                needs_recreate = True
            elif "    " in content or "---" in product_id or "---" in manifest_title or "/" in manifest_title:
                # 제목이나 ID가 깨진 경우 (빈 공간이 많거나 대시가 너무 많음, 또는 슬래시 포함)
                logger.info(f"[{product_id}] Broken formatting or characters detected. Recreating...")
                needs_recreate = True

        if needs_recreate:
            try:
                # 재생성을 위한 데이터 복구 (bulk_regenerate_promos.py 로직 차용)
                manifest_path = p_dir / "manifest.json"
                schema_path = p_dir / "product_schema.json"
                recovered_data = {}
                
                if manifest_path.exists():
                    m = json.loads(manifest_path.read_text(encoding="utf-8"))
                    recovered_data["title"] = m.get("title")
                    recovered_data["topic"] = m.get("topic")
                    recovered_data["price_usd"] = m.get("metadata", {}).get("final_price_usd", 29.0)
                
                if not recovered_data.get("title") and schema_path.exists():
                    schema = json.loads(schema_path.read_text(encoding="utf-8"))
                    recovered_data["title"] = schema.get("title")
                    recovered_data["topic"] = schema.get("sections", {}).get("hero", {}).get("subheadline", "")
                    price_str = schema.get("pricing", {}).get("price", "$29").replace("$", "")
                    try: recovered_data["price_usd"] = float(price_str)
                    except: recovered_data["price_usd"] = 29.0
                
                if not recovered_data.get("title"):
                    # Fallback to English MD
                    en_md = p_dir / "product_en.md"
                    if en_md.exists():
                        text = en_md.read_text(encoding="utf-8")
                        for line in text.splitlines():
                            if line.startswith("# "): recovered_data["title"] = line[2:].strip()
                
                if not recovered_data.get("title"):
                    logger.warning(f"[{product_id}] Could not recover info for recreation. Skipping.")
                    continue

                # 재생성 실행
                generate_promotions(
                    product_dir=p_dir,
                    product_id=product_id,
                    title=recovered_data["title"],
                    topic=recovered_data["topic"] or recovered_data["title"],
                    price_usd=recovered_data.get("price_usd", 29.0)
                )
                recreated_count += 1
                logger.info(f"[{product_id}] Successfully recreated high-quality English promotion.")
                
                # 재생성된 경우 기존 발행 여부와 상관없이 다시 발행 시도 (업데이트 목적)
                logger.info(f"[{product_id}] Re-publishing updated content...")
                try:
                    dispatch_publish(product_id)
                    published_count += 1
                except Exception as e:
                    logger.error(f"[{product_id}] Re-publishing failed: {e}")
            except Exception as e:
                logger.error(f"[{product_id}] Error during recreation: {e}")
                continue
        
        # 3. 고품질인 경우 자동 배포 (이미 배포된 경우는 건너뜀)
        results_path = promotions_dir / "publish_results.json"
        is_published = False
        if results_path.exists():
            try:
                res_data = json.loads(results_path.read_text(encoding="utf-8"))
                sent_list = res_data.get("sent", [])
                is_published = any(s.get("channel") == "blog_wordpress" and s.get("ok") for s in sent_list)
            except:
                pass
        
        if not is_published:
            # 고품질 검증 다시 한 번 (재생성 직후거나 기존 것이 좋거나)
            blog_md_path = promotions_dir / "blog_longform.md"
            if blog_md_path.exists():
                content = blog_md_path.read_text(encoding="utf-8")
                # 고품질 기준: 800자 이상, 영어만
                if len(content) >= 800 and not any(0xAC00 <= ord(c) <= 0xD7A3 for c in content):
                    logger.info(f"[{product_id}] High quality confirmed. Auto-publishing...")
                    try:
                        dispatch_publish(product_id)
                        published_count += 1
                    except Exception as e:
                        logger.error(f"[{product_id}] Error during auto-publish: {e}")

    logger.info(f"Analysis and Redeploy finished. Recreated: {recreated_count}, Published: {published_count}")

if __name__ == "__main__":
    analyze_and_redeploy()
