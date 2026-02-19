import os
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

def test_env_loading():
    print("--- Environment Loading Test ---")
    
    # 1. VERCEL 환경 시뮬레이션 해제
    os.environ.pop("VERCEL", None)
    os.environ.pop("NOW_REGION", None)
    
    # 2. _vercel_common 임포트 (이때 _ensure_env()가 실행됨)
    from api._vercel_common import _ensure_env
    
    print(f"Project Root: {root}")
    
    # 3. 환경 변수 확인 (예: UPSTASH_REDIS_REST_URL)
    upstash_url = os.getenv("UPSTASH_REDIS_REST_URL")
    upstash_token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
    
    print(f"UPSTASH_REDIS_REST_URL: {'Loaded' if upstash_url else 'Not Loaded'}")
    print(f"UPSTASH_REDIS_REST_TOKEN: {'Loaded' if upstash_token else 'Not Loaded'}")
    
    if upstash_url and upstash_token:
        print("SUCCESS: Environment variables loaded correctly from local files.")
    else:
        print("WARNING: Some environment variables are missing. Check .env or data/secrets.json.")

if __name__ == "__main__":
    test_env_loading()
