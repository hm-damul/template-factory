# -*- coding: utf-8 -*-
# 목적:
# 1) NOWPayments 대시보드를 브라우저로 자동 오픈한다.
# 2) 사용자가 로그인하고 API 키 화면까지 이동한다.
# 3) 사용자가 API 키를 "복사"해서 터미널에 붙여넣으면,
# 4) 스크립트가 .env에 NOWPAYMENTS_API_KEY를 자동 저장한다.
#
# 주의:
# - "키 발급(생성)" 자체는 대시보드 UI 정책/캡차/2FA 때문에 완전 자동이 어려울 수 있다.
# - 대신 브라우저를 정확한 페이지로 열고, 마지막 입력/저장을 자동화하는 방식이 안정적이다.

import os  # 운영체제 환경변수 접근용
from pathlib import Path  # 경로 처리를 안전하게 하기 위함

from dotenv import load_dotenv, set_key  # .env 로드/저장용
from playwright.sync_api import sync_playwright  # 브라우저 자동화용

# 프로젝트 루트 경로를 계산한다 (tools 폴더의 상위가 루트라고 가정)
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# .env 파일 경로를 지정한다
ENV_PATH = PROJECT_ROOT / ".env"

# NOWPayments 대시보드의 "API 키" 설정 페이지 URL
# (스크린샷에 보이는 store-settings#keys 를 기준으로 설정)
NOWPAYMENTS_KEYS_URL = "https://account.nowpayments.io/store-settings#keys"

# NOWPayments 대시보드의 "지갑(지급 지갑) 설정" 관련 화면으로 유도하려고 별도 URL도 준비
# UI가 바뀔 수 있으므로, 일단 설정 홈으로 이동시키는 방식으로 둔다
NOWPAYMENTS_SETTINGS_URL = "https://account.nowpayments.io/store-settings"


def ensure_env_file_exists() -> None:
    # .env 파일이 없으면 빈 파일을 만든다
    if not ENV_PATH.exists():
        ENV_PATH.write_text("", encoding="utf-8")


def save_env_value(key_name: str, value: str) -> None:
    # .env 파일이 존재하도록 보장한다
    ensure_env_file_exists()

    # python-dotenv의 set_key로 .env에 "키=값" 형태로 저장한다
    # (이미 있으면 덮어쓴다)
    set_key(str(ENV_PATH), key_name, value)


def read_env_value(key_name: str) -> str:
    # 현재 .env를 로딩한다 (override=True로 OS 환경변수도 덮어씌운다)
    load_dotenv(dotenv_path=str(ENV_PATH), override=True)

    # 환경변수에서 값을 읽는다 (없으면 빈 문자열)
    return (os.getenv(key_name) or "").strip()


def open_dashboard_and_wait_login() -> None:
    # Playwright로 브라우저를 실행한다
    with sync_playwright() as p:
        # 크로미움 브라우저 실행 (headless=False: 화면에 보여줌)
        browser = p.chromium.launch(headless=False)

        # 새 브라우저 컨텍스트 생성
        context = browser.new_context()

        # 새 페이지 생성
        page = context.new_page()

        # 1) API 키 페이지로 이동한다
        print("\n[1/3] NOWPayments 'API 키' 페이지를 브라우저로 엽니다...")
        page.goto(NOWPAYMENTS_KEYS_URL, wait_until="domcontentloaded")

        # 2) 사용자가 로그인/2FA/캡차 등을 처리하도록 안내한다
        print("\n[안내]")
        print("브라우저에서 NOWPayments에 로그인하세요.")
        print("로그인 후에도 자동으로 keys 페이지로 이동합니다.")
        print("API 키가 보이는 화면까지 이동한 다음, 아래 단계로 진행합니다.")

        # 3) 사용자가 준비되면 Enter
        input("\n준비되면 Enter를 누르세요(키를 터미널에 붙여넣는 단계로 진행)...")

        # 4) 브라우저는 그대로 둔 채로 종료한다
        # (사용자가 복사/확인할 수 있게)
        # 단, 여기서는 스크립트가 계속 실행되므로 브라우저는 열린 상태로 유지한다

        # 사용자가 키를 붙여넣는 입력 단계
        print("\n[2/3] NOWPayments 대시보드에서 API Key를 복사하세요.")
        print("그리고 아래에 그대로 붙여넣고 Enter를 누르세요.")
        api_key = input("NOWPAYMENTS_API_KEY = ").strip()

        # 입력값 최소 검증
        if not api_key or len(api_key) < 10:
            print("\n[ERROR] 입력된 키가 너무 짧거나 비어있습니다. 종료합니다.")
            browser.close()
            return

        # .env에 저장
        save_env_value("NOWPAYMENTS_API_KEY", api_key)

        # 저장 확인
        saved = read_env_value("NOWPAYMENTS_API_KEY")
        print("\n[3/3] .env 저장 완료")
        print(f".env 경로: {ENV_PATH}")
        print(f"저장된 키 미리보기: {saved[:6]}...{saved[-4:]}")

        # (선택) 지갑 등록 화면으로 유도
        print("\n[추가 안내: 지갑 등록]")
        print("이제 '지갑(지급 지갑)' 등록이 필요하면, 아래 페이지에서 1회 설정하세요.")
        print(NOWPAYMENTS_SETTINGS_URL)
        print(
            "\n지갑 등록 추천 조합(메타마스크 기준): USDT (BSC/BEP20) 또는 USDC (BSC/BEP20)"
        )
        print("※ ETH(ERC20 메인넷)은 수수료가 비싸 초기엔 비추천입니다.")

        # 브라우저 종료
        browser.close()


def main() -> None:
    # 프로젝트 루트/환경파일 위치 출력
    print("[INFO] Project root:", PROJECT_ROOT)
    print("[INFO] .env path:", ENV_PATH)

    # 기존 저장된 키가 이미 있는지 확인
    existing = read_env_value("NOWPAYMENTS_API_KEY")

    if existing:
        print("\n[INFO] 이미 .env에 NOWPAYMENTS_API_KEY가 존재합니다.")
        print(f"미리보기: {existing[:6]}...{existing[-4:]}")
        print("그래도 다시 설정하려면 계속 진행하세요.\n")

    # 대시보드 오픈 + 사용자 입력을 받아 저장
    open_dashboard_and_wait_login()


if __name__ == "__main__":
    main()
