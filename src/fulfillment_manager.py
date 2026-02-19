import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict

import jwt

from .config import Config
from .ledger_manager import LedgerManager
from .utils import ProductionError, get_logger, handle_errors

logger = get_logger(__name__)


class FulfillmentManager:
    """결제 완료된 주문에 대한 통제된 다운로드 이행을 관리하는 클래스"""

    def __init__(self, ledger_manager: LedgerManager):
        self.ledger_manager = ledger_manager
        self.jwt_secret = Config.JWT_SECRET_KEY
        self.token_expiry_seconds = Config.DOWNLOAD_TOKEN_EXPIRY_SECONDS

        if not self.jwt_secret:
            raise ProductionError(
                "JWT_SECRET_KEY 환경 변수가 설정되지 않았습니다.",
                stage="FulfillmentManager Init",
            )
        logger.info(
            f"FulfillmentManager 초기화 완료. 토큰 만료 시간: {self.token_expiry_seconds}초"
        )

    @handle_errors(stage="Token Generation")
    def generate_download_token(self, order_id: str, product_id: str) -> Dict[str, Any]:
        """지정된 주문 및 제품 ID에 대한 보안 다운로드 토큰을 생성합니다."""
        logger.info(
            f"다운로드 토큰 생성 요청 - 주문 ID: {order_id}, 제품 ID: {product_id}"
        )

        order_info = self.ledger_manager.get_order(order_id)
        if not order_info or order_info["status"] != "PAID":
            raise ProductionError(
                f"결제되지 않았거나 존재하지 않는 주문입니다: {order_id}",
                stage="Token Generation",
                original_exception="Order not PAID",
            )

        # 이미 토큰이 발급되었고 사용되지 않았다면 기존 토큰 재사용 (옵션)
        if (
            order_info.get("download_token")
            and not order_info.get("token_used")
            and order_info.get("token_expiry") > datetime.now().isoformat()
        ):
            logger.info(f"기존 유효한 토큰 재사용 - 주문 ID: {order_id}")
            return {
                "ok": True,
                "download_token": order_info["download_token"],
                "token_expiry": order_info["token_expiry"],
            }

        expiry_time = datetime.now() + timedelta(seconds=self.token_expiry_seconds)
        token_payload = {
            "order_id": order_id,
            "product_id": product_id,
            "exp": expiry_time.timestamp(),  # 토큰 만료 시간 (UNIX 타임스탬프)
            "iat": datetime.now().timestamp(),  # 발행 시간
            "jti": str(uuid.uuid4()),  # JWT ID (일회성 토큰을 위한 고유 ID)
        }

        # 토큰 서명
        token = jwt.encode(token_payload, self.jwt_secret, algorithm="HS256")

        # 원장에 토큰 정보 업데이트
        self.ledger_manager.update_order_status(
            order_id=order_id,
            download_token=token,
            token_expiry=expiry_time,
            token_used=False,  # 새 토큰이므로 사용되지 않음
        )

        logger.info(
            f"다운로드 토큰 생성 성공 - 주문 ID: {order_id}, 토큰 만료: {expiry_time}"
        )
        return {
            "ok": True,
            "download_token": token,
            "token_expiry": expiry_time.isoformat(),
        }

    @handle_errors(stage="Token Validation")
    def validate_download_token(self, token: str) -> Dict[str, Any]:
        """다운로드 토큰의 유효성을 검사하고 관련 주문/제품 정보를 반환합니다."""
        logger.info("다운로드 토큰 유효성 검사 시작")
        try:
            # 토큰 디코딩 및 검증 (만료 시간 자동 검증)
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            order_id = payload.get("order_id")
            product_id = payload.get("product_id")
            jti = payload.get("jti")  # JWT ID

            if not order_id or not product_id or not jti:
                raise ProductionError(
                    "토큰 페이로드에 필수 정보가 누락되었습니다.",
                    stage="Token Validation",
                    original_exception="Invalid Token Payload",
                )

            # 원장에서 주문 정보 조회
            order_info = self.ledger_manager.get_order(order_id)
            if not order_info:
                raise ProductionError(
                    f"원장에서 주문을 찾을 수 없습니다: {order_id}",
                    stage="Token Validation",
                    original_exception="Order not found",
                )

            if order_info["status"] != "PAID":
                raise ProductionError(
                    f"주문이 결제되지 않았습니다: {order_id}",
                    stage="Token Validation",
                    original_exception="Order not PAID",
                )

            # 토큰이 이미 사용되었는지 확인 (일회성 또는 사용 횟수 제한)
            if order_info.get("token_used"):
                raise ProductionError(
                    f"토큰이 이미 사용되었습니다: {order_id}",
                    stage="Token Validation",
                    original_exception="Token already used",
                )

            # 현재 발급된 토큰과 일치하는지 확인 (여러 토큰 발급 방지)
            if order_info.get("download_token") != token:
                raise ProductionError(
                    f"유효하지 않은 토큰입니다 (불일치): {order_id}",
                    stage="Token Validation",
                    original_exception="Token mismatch",
                )

            logger.info(
                f"다운로드 토큰 유효성 검사 성공 - 주문 ID: {order_id}, 제품 ID: {product_id}"
            )
            return {
                "ok": True,
                "order_id": order_id,
                "product_id": product_id,
                "jti": jti,
            }

        except jwt.ExpiredSignatureError:
            raise ProductionError(
                "다운로드 토큰이 만료되었습니다.",
                stage="Token Validation",
                original_exception="Token Expired",
            )
        except jwt.InvalidTokenError as e:
            raise ProductionError(
                f"유효하지 않은 다운로드 토큰입니다: {e}",
                stage="Token Validation",
                original_exception=e,
            )
        except Exception as e:
            raise ProductionError(
                f"토큰 유효성 검사 중 예기치 않은 오류 발생: {e}",
                stage="Token Validation",
                original_exception=e,
            )

    @handle_errors(stage="Fulfillment")
    def fulfill_download(
        self, token: str, ip_address: str, user_agent: str
    ) -> Dict[str, Any]:
#         """유효한 토큰으로 제품 다운로드를 이행하고 이력을 기록합니다."""
        logger.info(f"다운로드 이행 요청 - IP: {ip_address}, User-Agent: {user_agent}")

        # 1. 토큰 유효성 검사
        token_validation_result = self.validate_download_token(token)
        order_id = token_validation_result["order_id"]
        product_id = token_validation_result["product_id"]
        jti = token_validation_result["jti"]

        # 2. 제품 정보 조회 (패키지 경로)
        product_info = self.ledger_manager.get_product(product_id)
        if not product_info or not product_info.get("package_path"):
            raise ProductionError(
                f"제품 패키지 경로를 찾을 수 없습니다: {product_id}",
                stage="Fulfillment",
                product_id=product_id,
            )
        package_path = product_info["package_path"]

        if not os.path.exists(package_path):
            raise ProductionError(
                f"실제 제품 파일이 서버에 존재하지 않습니다: {package_path}",
                stage="Fulfillment",
                product_id=product_id,
            )

        # 3. 다운로드 이력 기록
        download_id = str(uuid.uuid4())
        self.ledger_manager.record_download(
            download_id=download_id,
            order_id=order_id,
            product_id=product_id,
            ip_address=ip_address,
            user_agent=user_agent,
            token_used=token,  # 사용된 토큰 자체를 기록
        )

        # 4. 토큰 사용 완료 표시 (일회성 토큰의 경우)
        self.ledger_manager.update_order_status(order_id=order_id, token_used=True)

        logger.info(
            f"다운로드 이행 성공 - 주문 ID: {order_id}, 제품 ID: {product_id}, 파일: {package_path}"
        )
        return {"ok": True, "download_path": package_path, "download_id": download_id}


# -----------------------------
# 로컬 단독 실행 테스트 (선택 사항)
# -----------------------------

if __name__ == "__main__":
    logger.info("FulfillmentManager 모듈 로컬 테스트 시작")

    ledger = LedgerManager()

    # 테스트를 위한 더미 환경 변수 설정 (실제 .env 파일 사용을 권장)
    os.environ["JWT_SECRET_KEY"] = "supersecretkey_for_test_fulfillment"
    os.environ["DOWNLOAD_TOKEN_EXPIRY_SECONDS"] = "5"  # 5초 후 만료
    os.environ["DATABASE_URL"] = "sqlite:///./test_product_factory.db"

    # Config 클래스 재로드 (환경 변수 변경 후)
    from importlib import reload

    from . import config

    reload(config)
    from .config import Config  # 업데이트된 Config 로드

    fulfillment_manager = FulfillmentManager(ledger)

    test_product_id = "test-fulfill-product-001"
    test_order_id = str(uuid.uuid4())
    test_customer_email = "fulfill@example.com"
    test_package_path = os.path.join(
        Config.DOWNLOAD_DIR, f"{test_product_id}-packaged.zip"
    )

    # 테스트를 위한 제품 및 주문 원장 항목 생성 및 상태 업데이트
    try:
        ledger.create_product(
            test_product_id,
            "Test Product for Fulfillment",
            metadata={"initial": "data"},
        )
        ledger.update_product_status(
            test_product_id,
            "PUBLISHED",
            package_path=test_package_path,
            checksum="dummy_checksum_ffm",
            version="1.0.0",
        )

        ledger.create_order(test_order_id, test_product_id, test_customer_email, 100)
        ledger.update_order_status(test_order_id, "PAID")
        logger.info("테스트 제품 및 주문 원장에 추가 완료.")

        # 더미 패키지 파일 생성
        ensure_parent_dir(test_package_path)
        with open(test_package_path, "w") as f:
            f.write("dummy fulfillment content")

        # 1. 다운로드 토큰 생성 테스트
        token_result = fulfillment_manager.generate_download_token(
            test_order_id, test_product_id
        )
        token = token_result["download_token"]
        logger.info("다운로드 토큰 생성 결과:")
        logger.info(json.dumps(token_result, ensure_ascii=False, indent=2))

        # 2. 토큰 유효성 검사 테스트
        logger.info("\n--- 토큰 유효성 검사 테스트 (유효) ---")
        validation_result = fulfillment_manager.validate_download_token(token)
        logger.info(f"유효성 검사 결과: {validation_result}")

        # 3. 다운로드 이행 테스트
        logger.info("\n--- 다운로드 이행 테스트 ---")
        fulfillment_result = fulfillment_manager.fulfill_download(
            token, "127.0.0.1", "Test-Agent/1.0"
        )
        logger.info("다운로드 이행 결과:")
        logger.info(json.dumps(fulfillment_result, ensure_ascii=False, indent=2))

        # 4. 사용된 토큰 재사용 시도 (실패 예상)
        logger.info("\n--- 사용된 토큰 재사용 테스트 (실패 예상) ---")
        try:
            fulfillment_manager.fulfill_download(token, "127.0.0.1", "Test-Agent/1.0")
        except ProductionError as pe:
            logger.info(f"예상된 오류 발생: {pe.message}")

        # 5. 만료된 토큰 테스트 (기다린 후 시도)
        logger.info("\n--- 만료된 토큰 테스트 (5초 대기) ---")
        import time

        time.sleep(6)  # 토큰 만료 시간보다 길게 대기
        try:
            fulfillment_manager.fulfill_download(token, "127.0.0.1", "Test-Agent/1.0")
        except ProductionError as pe:
            logger.info(f"예상된 오류 발생: {pe.message}")

    except ProductionError as pe:
        logger.error(f"생산 오류 발생: {pe.message}")
        if pe.original_exception:
            logger.error(f"원본 예외: {pe.original_exception}")
    except Exception as e:
        logger.error(f"예기치 않은 오류 발생: {e}")
    finally:
        # 테스트 후 생성된 파일 및 디렉토리 정리
        if os.path.exists(test_package_path):
            os.remove(test_package_path)
            logger.info(f"테스트 패키지 파일 정리: {test_package_path}")

        # DB 파일 삭제 (테스트용이므로)
        if os.path.exists("test_product_factory.db"):
            os.remove("test_product_factory.db")
            logger.info("테스트 DB 파일 삭제: test_product_factory.db")

    logger.info("FulfillmentManager 모듈 로컬 테스트 완료")
