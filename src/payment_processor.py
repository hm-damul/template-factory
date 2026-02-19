import json
import os
import uuid
from typing import Any, Dict

import requests

from .config import Config
from .ledger_manager import LedgerManager
from .utils import ProductionError, get_logger, handle_errors, retry_on_failure

logger = get_logger(__name__)


class PaymentProcessor:
    """Lemon Squeezy API를 통해 결제를 처리하고 주문 상태를 관리하는 클래스"""

    LEMON_SQUEEZY_API_BASE = "https://api.lemonsqueezy.com/v1"
    # Lemon Squeezy에 제품 ID를 매핑하는 사전 (실제 제품에 따라 업데이트 필요)
    # 예: {"product_id_from_our_system": "lemon_squeezy_variant_id"}
    PRODUCT_VARIANT_MAP = {
        "test-crypto-landing-page-001": 99999,  # 예시 Variant ID, 실제 Lemon Squeezy 대시보드에서 확인 필요
        "test-package-product-001": 99999,
        "test-publish-product-001": 99999,
    }

    def __init__(self, ledger_manager: LedgerManager):
        self.ledger_manager = ledger_manager
        self.api_key = Config.LEMON_SQUEEZY_API_KEY
        if not self.api_key:
            raise ProductionError(
                "LEMON_SQUEEZY_API_KEY 환경 변수가 설정되지 않았습니다.",
                stage="PaymentProcessor Init",
            )
        logger.info("PaymentProcessor 초기화 완료")

    def _get_headers(self) -> Dict[str, str]:
        """Lemon Squeezy API 요청에 필요한 헤더를 반환합니다."""
        return {
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/vnd.api+json",
            "Authorization": f"Bearer {self.api_key}",
        }

    @handle_errors(stage="Payment Gate")
    @retry_on_failure(max_retries=3)
    def create_checkout(
        self, product_id: str, customer_email: str, quantity: int = 1
    ) -> Dict[str, Any]:
#         """Lemon Squeezy를 통해 체크아웃 세션을 생성하고 체크아웃 URL을 반환합니다."""
        logger.info(
            f"체크아웃 생성 요청 - 제품 ID: {product_id}, 이메일: {customer_email}"
        )

        variant_id = self.PRODUCT_VARIANT_MAP.get(product_id)
        if not variant_id:
            raise ProductionError(
                f"Lemon Squeezy 제품 Variant ID를 찾을 수 없습니다: {product_id}",
                stage="Payment Gate",
                product_id=product_id,
            )

        order_id = str(uuid.uuid4())  # 내부 주문 ID 생성

        # 원장에 PENDING 상태의 주문 기록
        self.ledger_manager.create_order(
            order_id=order_id,
            product_id=product_id,
            customer_email=customer_email,
            amount=0,  # 초기 금액은 0 (Lemon Squeezy에서 실제 금액 결정)
            currency="USD",
            payment_details={
                "lemon_squeezy_variant_id": variant_id,
                "status": "pending",
            },
        )

        payload = {
            "data": {
                "type": "checkouts",
                "attributes": {
                    "checkout_data": {
                        "email": customer_email,
                        "custom": {
                            "order_id": order_id,  # 웹훅으로 다시 받을 수 있도록 사용자 정의 데이터 추가
                            "product_id": product_id,
                        },
                    },
                    "product_options": {"quantity": quantity},
                },
                "relationships": {
                    "variant": {"data": {"type": "variants", "id": str(variant_id)}}
                },
            }
        }

        try:
            response = requests.post(
                f"{self.LEMON_SQUEEZY_API_BASE}/checkouts",
                headers=self._get_headers(),
                data=json.dumps(payload),
            )
            response.raise_for_status()  # HTTP 오류 발생 시 예외 처리

            checkout_data = response.json()
            checkout_url = checkout_data["data"]["attributes"]["url"]
            lemon_squeezy_checkout_id = checkout_data["data"]["id"]

            # 원장 주문 정보 업데이트 (Lemon Squeezy 체크아웃 ID 기록)
            self.ledger_manager.update_order_status(
                order_id=order_id,
                status="PENDING",
                payment_details={
                    "lemon_squeezy_variant_id": variant_id,
                    "lemon_squeezy_checkout_id": lemon_squeezy_checkout_id,
                    "checkout_url": checkout_url,
                    "status": "pending",
                },
            )

            logger.info(
                f"체크아웃 생성 성공 - 주문 ID: {order_id}, 체크아웃 URL: {checkout_url}"
            )
            return {
                "ok": True,
                "order_id": order_id,
                "checkout_url": checkout_url,
                "lemon_squeezy_checkout_id": lemon_squeezy_checkout_id,
            }
        except requests.exceptions.RequestException as e:
            error_msg = f"Lemon Squeezy 체크아웃 생성 API 요청 실패: {e}"
            if e.response is not None:
                error_msg += f", 응답: {e.response.text}"
            raise ProductionError(
                error_msg,
                stage="Payment Gate",
                product_id=product_id,
                original_exception=e,
            )
        except Exception as e:
            raise ProductionError(
                f"체크아웃 생성 중 예기치 않은 오류 발생: {e}",
                stage="Payment Gate",
                product_id=product_id,
                original_exception=e,
            )

    @handle_errors(stage="Payment Webhook")
    def handle_webhook_event(self, event_data: Dict[str, Any]):
        """Lemon Squeezy 웹훅 이벤트를 처리하여 주문 상태를 업데이트합니다."""
        event_type = event_data.get("meta", {}).get("event_name")
        logger.info(f"웹훅 이벤트 수신: {event_type}")

        if event_type == "order_created" or event_type == "order_updated":
            order_id = (
                event_data.get("data", {})
                .get("attributes", {})
                .get("first_order_item", {})
                .get("product_id")
            )  # TODO: custom data에서 order_id 추출 로직 확인
            # Lemon Squeezy 웹훅의 custom data는 checkout 생성 시 전달된 custom 필드에 접근해야 함
            # 실제 웹훅 페이로드 구조를 확인하여 `order_id`를 정확히 추출해야 합니다.
            # 현재는 더미로 product_id를 order_id로 사용합니다.
            # 임시 로직: custom 필드에서 order_id를 가져오기
            custom_data = event_data.get("meta", {}).get("custom", {})
            order_id = custom_data.get("order_id")
            product_id = custom_data.get("product_id")

            if not order_id:
                logger.error("웹훅 페이로드에서 order_id를 찾을 수 없습니다.")
                raise ProductionError(
                    "웹훅 처리 실패: order_id 누락", stage="Payment Webhook"
                )

            # 주문 상태 및 금액 추출
            status = event_data["data"]["attributes"]["status"]
            amount_usd_cents = event_data["data"]["attributes"]["total"]
            amount = amount_usd_cents / 100  # 센트를 달러로 변환
            currency = event_data["data"]["attributes"]["currency"]

            if status == "paid":
                new_status = "PAID"
                logger.info(
                    f"주문 결제 확인 - 주문 ID: {order_id}, 금액: {amount} {currency}"
                )
            elif status == "refunded":
                new_status = "REFUNDED"
                logger.info(f"주문 환불 확인 - 주문 ID: {order_id}")
            elif status == "failed":
                new_status = "FAILED"
                logger.warning(f"주문 결제 실패 - 주문 ID: {order_id}")
            else:
                new_status = "PENDING"  # 다른 상태는 PENDING으로 처리
                logger.info(
                    f"주문 상태 변경 - 주문 ID: {order_id}, 새 상태: {new_status}"
                )

            # 원장 업데이트
            self.ledger_manager.update_order_status(
                order_id=order_id, status=new_status, payment_details=event_data
            )

            # 결제 완료 시 추가 로직 (예: FulfillmentManager 호출)
            if new_status == "PAID":
                logger.info(
                    f"주문 {order_id} (제품 {product_id}) 결제 완료. 이행 처리 시작."
                )
                # TODO: FulfillmentManager 호출 로직 추가

            return {"ok": True, "order_id": order_id, "new_status": new_status}
        else:
            logger.info(f"처리할 필요 없는 웹훅 이벤트 유형: {event_type}")
            return {"ok": True, "message": f"Event type {event_type} not handled."}


# -----------------------------
# 로컬 단독 실행 테스트 (선택 사항)
# -----------------------------

if __name__ == "__main__":
    logger.info("PaymentProcessor 모듈 로컬 테스트 시작")

    ledger = LedgerManager()

    # 테스트를 위한 더미 환경 변수 설정 (실제 .env 파일 사용을 권장)
    os.environ["LEMON_SQUEEZY_API_KEY"] = "TEST_LEMON_SQUEEZY_API_KEY_123"
    os.environ["DATABASE_URL"] = "sqlite:///./test_product_factory.db"

    # Config 클래스 재로드 (환경 변수 변경 후)
    from importlib import reload

    from . import config

    reload(config)
    from .config import Config  # 업데이트된 Config 로드

    payment_processor = PaymentProcessor(ledger)

    test_product_id = "test-crypto-landing-page-001"
    test_customer_email = "customer@example.com"

    # 테스트 제품 원장에 추가
    try:
        ledger.create_product(test_product_id, "Test Product for Payment")
        logger.info("테스트 제품 원장에 추가 완료.")

        # 1. 체크아웃 생성 테스트
        checkout_result = payment_processor.create_checkout(
            test_product_id, test_customer_email
        )
        logger.info("체크아웃 생성 결과:")
        logger.info(json.dumps(checkout_result, ensure_ascii=False, indent=2))

        # 2. 웹훅 이벤트 처리 테스트 (결제 성공 시뮬레이션)
        # 실제 Lemon Squeezy 웹훅 페이로드 구조에 맞춰야 함
        dummy_webhook_paid_event = {
            "meta": {
                "event_name": "order_created",  # 또는 "order_updated"
                "custom": {
                    "order_id": checkout_result["order_id"],
                    "product_id": test_product_id,
                },
            },
            "data": {
                "id": "evt_12345",
                "type": "orders",
                "attributes": {
                    "status": "paid",
                    "total": 2900,  # $29.00
                    "currency": "USD",
                    "first_order_item": {
                        "product_id": "some_internal_lemon_squeezy_id"
                    },
                },
            },
        }

        logger.info("\n--- 웹훅 이벤트 처리 테스트 (결제 성공) ---")
        webhook_result_paid = payment_processor.handle_webhook_event(
            dummy_webhook_paid_event
        )
        logger.info("웹훅 처리 결과:")
        logger.info(json.dumps(webhook_result_paid, ensure_ascii=False, indent=2))

        final_order_info = ledger.get_order(checkout_result["order_id"])
        logger.info(f"최종 주문 상태: {final_order_info.get('status')}")

    except ProductionError as pe:
        logger.error(f"생산 오류 발생: {pe.message}")
        if pe.original_exception:
            logger.error(f"원본 예외: {pe.original_exception}")
    except Exception as e:
        logger.error(f"예기치 않은 오류 발생: {e}")

    logger.info("PaymentProcessor 모듈 로컬 테스트 완료")
