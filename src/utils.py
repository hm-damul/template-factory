import hashlib
import json
import logging
import os
from functools import wraps
from typing import Any

# 프로젝트 루트 경로 계산
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 로그 파일 경로 설정
LOG_FILE = os.getenv(
    "LOG_FILE", os.path.join(PROJECT_ROOT, "logs", "product_factory.log")
)

# 로그 디렉토리 생성 (존재하지 않을 경우)
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# 로거 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
)


def get_logger(name):
    """이름을 기준으로 로거 인스턴스를 반환합니다."""
    return logging.getLogger(name)


# 공통 로거 인스턴스
logger = get_logger(__name__)


class ProductionError(Exception):
    """생산 파이프라인 관련 오류를 위한 사용자 정의 예외 클래스"""

    def __init__(
        self, message, stage="Unknown", product_id=None, original_exception=None
    ):
        super().__init__(message)
        self.message = message
        self.stage = stage
        self.product_id = product_id
        self.original_exception = original_exception
        logger.error(
            f"[ProductionError] Stage: {self.stage}, Product ID: {self.product_id}, Message: {self.message}, Original: {self.original_exception}"
        )


def handle_errors(stage):
    """
    함수 실행 중 발생하는 예외를 처리하고 로깅하는 데 사용되는 데코레이터.
    ProductionError로 캡슐화하여 일관된 오류 보고를 제공합니다.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            product_id = kwargs.get("product_id") or (
                args[0].product_id if hasattr(args[0], "product_id") else None
            )
            try:
                return func(*args, **kwargs)
            except ProductionError as e:
                # 이미 ProductionError인 경우 다시 캡슐화하지 않음
                raise e
            except Exception as e:
                # 다른 모든 예외를 ProductionError로 캡슐화
                error_message = f"'{func.__name__}' 함수 실행 중 오류 발생: {e}"
                raise ProductionError(
                    error_message,
                    stage=stage,
                    product_id=product_id,
                    original_exception=e,
                )

        return wrapper

    return decorator


def retry_on_failure(
    max_retries=3, delay_seconds=1, catch_exceptions=(ProductionError,)
):  # ProductionError 추가
#     """
#     실패 시 지정된 횟수만큼 재시도하는 데코레이터.
#     """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            product_id = kwargs.get("product_id") or (
                args[0].product_id if hasattr(args[0], "product_id") else None
            )
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except catch_exceptions as e:
                    logger.warning(
                        f"Attempt {attempt}/{max_retries} for {func.__name__} failed (Product ID: {product_id}): {e}"
                    )
                    if attempt == max_retries:
                        logger.error(
                            f"All {max_retries} attempts for {func.__name__} failed (Product ID: {product_id})."
                        )
                        raise  # 마지막 시도 실패 시 예외 다시 발생
                    # 간단한 지연 후 재시도
                    import time

                    time.sleep(delay_seconds)
            return None  # 모든 재시도 실패 시 None 반환 (실제 사용 시 예외 발생 또는 기본값 처리 필요)

        return wrapper

    return decorator


def calculate_file_checksum(file_path: str) -> str:
    """파일의 SHA256 체크섬을 계산합니다."""
    h = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                h.update(chunk)
        return h.hexdigest()
    except FileNotFoundError:
        logger.error(f"체크섬 계산 실패: 파일을 찾을 수 없습니다 - {file_path}")
        raise ProductionError(
            f"체크섬 계산 실패: 파일을 찾을 수 없습니다 - {file_path}",
            stage="File Utility",
        )
    except Exception as e:
        logger.error(f"SHA256 체크섬 계산 중 오류 발생: {file_path}, 오류: {e}")
        raise ProductionError(f"체크섬 계산 실패: {e}", stage="File Utility")


def ensure_parent_dir(path: str) -> None:
    """파일의 부모 폴더를 생성합니다."""
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        try:
            os.makedirs(parent, exist_ok=True)
            logger.debug(f"디렉토리 생성: {parent}")
        except Exception as e:
            raise ProductionError(
                f"디렉토리 생성 실패: {parent}, 오류: {e}", stage="File Utility"
            )


def write_text(path: str, text: str) -> None:
    """UTF-8로 텍스트 파일을 저장합니다."""
    ensure_parent_dir(path)
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        logger.debug(f"텍스트 파일 저장: {path}")
    except Exception as e:
        raise ProductionError(
            f"텍스트 파일 저장 실패: {path}, 오류: {e}", stage="File Utility"
        )


def write_json(path: str, obj: Any) -> None:
    """JSON 파일을 저장합니다."""
    import json  # Ensure json is imported
    ensure_parent_dir(path)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        logger.debug(f"JSON 파일 저장: {path}")
    except Exception as e:
        raise ProductionError(
            f"JSON 파일 저장 실패: {path}, 오류: {e}", stage="File Utility"
        )
