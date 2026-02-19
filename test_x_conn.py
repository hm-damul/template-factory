import os
import sys
import json
from pathlib import Path

# 프로젝트 루트 추가
PROJECT_ROOT = Path(r"d:\auto\MetaPassiveIncome_FINAL")
sys.path.append(str(PROJECT_ROOT))

from social import x_twitter

def test_x_connection():
    # secrets.json에서 읽어오기
    secrets_path = PROJECT_ROOT / "data" / "secrets.json"
    with open(secrets_path, "r", encoding="utf-8") as f:
        secrets = json.load(f)
    
    # 환경 변수에 설정 (x_twitter.py가 여기서 읽음)
    os.environ["X_CONSUMER_KEY"] = secrets.get("X_CONSUMER_KEY", "")
    os.environ["X_CONSUMER_SECRET"] = secrets.get("X_CONSUMER_SECRET", "")
    os.environ["X_ACCESS_TOKEN"] = secrets.get("X_ACCESS_TOKEN", "")
    os.environ["X_ACCESS_TOKEN_SECRET"] = secrets.get("X_ACCESS_TOKEN_SECRET", "")
    os.environ["X_BEARER_TOKEN"] = secrets.get("X_BEARER_TOKEN", "")
    os.environ["SOCIAL_MOCK"] = "0"

    print("Testing X (Twitter) connection...")
    log_dir = PROJECT_ROOT / "logs" / "test_x"
    res = x_twitter.post_text("Test post from MetaPassiveIncome system #test #api", log_dir)
    
    print(f"Result: {res}")
    if res.get("ok") and res.get("mode") == "real":
        print("SUCCESS: X connection verified.")
        return True
    elif res.get("mode") == "mock":
        print("MOCK: X is in mock mode (likely missing keys or explicit mock).")
        return False
    else:
        print(f"FAILED: X connection failed. {res}")
        return False

if __name__ == "__main__":
    test_x_connection()
