
import os
import json
import time
from pathlib import Path
from src.ledger_manager import LedgerManager
from src.config import Config
from auto_pilot import ProductFactory
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("auto_heal")

def auto_heal():
    lm = LedgerManager(Config.DATABASE_URL)
    factory = ProductFactory()
    
    products = lm.list_products()
    # 실패한 제품들 필터링
    failed = [p for p in products if 'FAILED' in p.get('status', '')]
    
    if not failed:
        logger.info("복구할 실패 제품이 없습니다.")
        return

    logger.info(f"총 {len(failed)}개의 실패 제품 복구 시도 중...")
    
    for p in failed:
        pid = p['id']
        status = p['status']
        topic = p.get('topic', 'Unknown')
        meta = p.get('metadata')
        if isinstance(meta, str):
            try: meta = json.loads(meta)
            except: meta = {}
        
        error_msg = str(meta.get('error', '')).lower()
        stage = meta.get('stage', '')
        
        logger.info(f"복구 시도: {pid} (상태: {status}, 단계: {stage})")
        
        # 1. Vercel 프로젝트 한도 오류였던 경우 -> 이제 cleanup 로직이 있으니 바로 재발행 시도
        if "too_many_projects" in error_msg:
            logger.info(f"  -> Vercel 한도 오류 감지. 재발행 시도...")
            output_dir = Path(Config.OUTPUT_DIR) / pid
            if output_dir.exists() and factory.publisher:
                try:
                    res = factory.publisher.publish_product(pid, str(output_dir))
                    if res.get('status') == 'PUBLISHED':
                        logger.info(f"  [성공] {pid} 재발행 완료")
                        continue
                except Exception as e:
                    logger.error(f"  [실패] {pid} 재발행 오류: {e}")
        
        # 2. 기타 단계 실패 -> 전체 파이프라인 재실행 또는 재개
        logger.info(f"  -> 파이프라인 복구 시도 (Topic: {topic})...")
        try:
            output_dir = Path(Config.OUTPUT_DIR) / pid
            # 파일이 아예 없으면 새로 생성, 있으면 재개
            if not output_dir.exists() or not (output_dir / "index.html").exists():
                logger.info(f"  -> 출력물 누락. 새로 생성합니다.")
                # 새로 생성하면 ID가 달라지지만, auto_pilot 기본 동작임
                result = factory.create_and_process_product(topic, ["en"])
            else:
                logger.info(f"  -> 기존 파일 발견. 파이프라인 재개 시도...")
                result = factory.resume_processing_product(pid, topic, str(output_dir))
            
            logger.info(f"  [결과] {pid} 복구 결과: {result.status}")
        except Exception as e:
            logger.error(f"  [실패] {pid} 복구 오류: {e}")

if __name__ == "__main__":
    auto_heal()
