
import asyncio
import sys
from pathlib import Path
from src.utils import get_logger
from auto_pilot import ProductFactory

logger = get_logger("recovery")

async def recover_product():
    product_id = "20260213-154551-프리랜서-컨설턴트-서비스-소개-랜딩-페이지"
    factory = ProductFactory()
    
    logger.info(f"상품 복구 시도: {product_id}")
    
    try:
        # ProductFactory의 resume_processing_product는 인스턴스 메서드입니다.
        # 필요한 인자: product_id, topic, current_product_output_dir
        
        # 1. 원장에서 정보 조회
        product_info = factory.ledger_manager.get_product(product_id)
        if not product_info:
            logger.error(f"상품 정보를 찾을 수 없습니다: {product_id}")
            return
            
        topic = "freelancer-consultant-landing-page" # 메타데이터나 파일명에서 유추
        # outputs 디렉토리 내의 상품 경로
        output_dir = str(factory.outputs_dir / product_id)
        
        # 2. 파이프라인 재개 (resume_processing_product는 일반 메서드임)
        result = factory.resume_processing_product(product_id, topic, output_dir)
        
        logger.info(f"상품 복구 프로세스 완료. 결과 상태: {result.status}")
        
    except Exception as e:
        logger.error(f"상품 복구 중 오류 발생: {e}")

if __name__ == "__main__":
    asyncio.run(recover_product())
