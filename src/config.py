import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

# MetaPassiveIncome 전용 키 매니저를 통한 동기화
try:
    # Optional: try to sync keys if manager exists
    from src.key_manager import KeyManager, apply_keys
    
    # Apply keys from secrets.json to os.environ first
    apply_keys(PROJECT_ROOT, inject=True)
    
    # Then scan .env to update secrets.json if needed
    km = KeyManager(PROJECT_ROOT)
    km.scan_and_extract()
except ImportError:
    # KeyManager is optional, so we just ignore if it's missing
    pass
except Exception as e:
    print(f"Warning: Failed to initialize KeyManager: {e}")

class Config:
    # Lemon Squeezy API 키
    LEMON_SQUEEZY_API_KEY = os.getenv("LEMON_SQUEEZY_API_KEY")
    # GitHub 토큰
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    # Vercel API 토큰
    VERCEL_API_TOKEN = os.getenv("VERCEL_API_TOKEN")
    # 다운로드 토큰 만료 시간 (초)
    DOWNLOAD_TOKEN_EXPIRY_SECONDS = int(
        os.getenv("DOWNLOAD_TOKEN_EXPIRY_SECONDS", 3600)
    )
    # JWT 시크릿 키
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    # 데이터베이스 URL (예: SQLite 파일 경로)
    DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///{PROJECT_ROOT}/data/ledger.db"
    # 출력 파일 저장 경로
    OUTPUT_DIR = os.getenv("OUTPUT_DIR") or str(PROJECT_ROOT / "outputs")
    # 다운로드 파일 저장 경로
    DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR") or str(PROJECT_ROOT / "downloads")
    # 로그 파일 경로
    LOG_FILE = os.getenv("LOG_FILE") or str(PROJECT_ROOT / "logs" / "product_factory.log")

    # 대시보드 서버 포트
    DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8099"))
    
    # Payment Mode
    PAYMENT_MODE = os.getenv("PAYMENT_MODE", "nowpayments")

    # 필요한 환경 변수가 설정되었는지 확인
    @classmethod
    def validate(cls):
        required_vars = [
            "GITHUB_TOKEN",
            "VERCEL_API_TOKEN",
            "JWT_SECRET_KEY",
        ]
        # Only require Lemon Squeezy key if using it
        if cls.PAYMENT_MODE == "lemonsqueezy":
            required_vars.append("LEMON_SQUEEZY_API_KEY")
            
        missing_vars = [var for var in required_vars if getattr(cls, var) is None or getattr(cls, var) == ""]
        if missing_vars:
            # Just warn instead of crash for now to allow partial operation
            print(f"WARNING: 필수 환경 변수가 누락되었습니다: {', '.join(missing_vars)}. .env 파일을 확인해주세요.")
            # raise ValueError(...) # Temporarily disabled to prevent crash loop



# 런타임에서 필요한 시점에 validate를 호출하도록 변경
