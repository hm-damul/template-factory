import argparse
import os
import sys
from pathlib import Path

# src 모듈 임포트
from src.config import Config
from src.product_factory import ProductFactory
from src.utils import ProductionError, get_logger

logger = get_logger(__name__)


def run_main_pipeline(topic: str, batch_size: int, languages: list[str]) -> int:
    """
    제품 생성부터 발행까지 전체 파이프라인을 실행하는 메인 함수.
    """
    logger.info("제품 생산 파이프라인 시작.")

    try:
        # Config 유효성 검사 (애플리케이션 시작 시)
        Config.validate()

        project_root = Path(os.path.dirname(os.path.abspath(__file__)))
        factory = ProductFactory(project_root)

        results = factory.run_batch(
            batch_size=batch_size, languages=languages, topic=topic
        )

        logger.info("=== 전체 파이프라인 배치 결과 ===")
        for r in results:
            logger.info(
                f"- 제품 ID: {r.product_id}, 상태: {r.status}, 출력 디렉토리: {r.output_dir}"
            )

        # 성공적으로 발행된 제품의 Vercel 배포 주소 보고
        published_products_urls = []
        for r in results:
            if r.status == "PUBLISHED":
                product_info = factory.ledger_manager.get_product(r.product_id)
                if product_info and product_info.get("metadata", {}).get(
                    "deployment_url"
                ):
                    published_products_urls.append(
                        f"제품 ID: {r.product_id}, URL: {product_info['metadata']['deployment_url']}"
                    )

        if published_products_urls:
            logger.info("\n--- 성공적으로 발행된 제품의 배포 URL ---")
            for url_info in published_products_urls:
                logger.info(url_info)
        else:
            logger.info("성공적으로 발행된 제품이 없습니다.")

        logger.info("제품 생산 파이프라인 완료.")
        return 0

    except ProductionError as pe:
        logger.critical(
            f"생산 파이프라인 치명적 오류 발생 (단계: {pe.stage}, 제품 ID: {pe.product_id}): {pe.message}",
            exc_info=True,
        )
        return 1
    except Exception as e:
        logger.critical(f"예기치 않은 치명적인 오류 발생: {e}", exc_info=True)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="디지털 제품 공장 자동화 파이프라인")
    parser.add_argument(
        "--topic",
        type=str,
        default="",
        help="생성할 제품의 주제 (비워두면 기본 주제 사용)",
    )
    parser.add_argument("--batch", type=int, default=1, help="생성할 제품의 배치 개수")
    parser.add_argument(
        "--languages",
        type=str,
        default="en,ko",
        help="쉼표로 구분된 언어 목록 (예: en,ko)",
    )

    args = parser.parse_args()

    languages = [s.strip().lower() for s in args.languages.split(",") if s.strip()]
    if not languages:
        languages = ["en", "ko"]  # 기본값

    return run_main_pipeline(args.topic, args.batch, languages)


if __name__ == "__main__":
    # 이 메인 스크립트는 `d:/auto/MetaPassiveIncome_FINAL` 디렉토리에서 직접 실행됨
    # `src` 디렉토리는 현재 스크립트 기준으로 상대 경로로 접근 가능
    sys.path.insert(
        0, str(Path(__file__).resolve().parent)
    )  # 현재 디렉토리를 sys.path에 추가
    sys.path.insert(
        0, str(Path(__file__).resolve().parent / "src")
    )  # src 디렉토리를 sys.path에 추가

    raise SystemExit(main())
