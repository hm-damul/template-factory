# 파일명: setup_all.py
import os


def initial_setup():
    # 1. 필요한 폴더 구조 자동 생성
    folders = ["templates", "outputs", "logs", "config"]
    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)
            print(f"폴더 생성 완료: {folder}")

    # 2. 맥락 유지용 초기 MD 파일 생성
    md_content = """# CATP Project Progress
- 상태: 초기화 완료
- 단계: 1단계 환경 설정
- 현재 작업: 프로젝트 구조 생성 및 환경 변수 수집 준비
"""
    with open("CATP_PROGRESS.md", "w", encoding="utf-8") as f:
        f.write(md_content)

    # 3. 환경 변수 설정 폼 (여기에 정보를 입력하면 .env가 생성됩니다)
    print("\n" + "=" * 30)
    print("CATP 자율 개발 설정 폼")
    print("=" * 30)
    gemini_key = input("1. Gemini API Key: ")
    wallet = input("2. Crypto Wallet Address (Payment): ")

    with open(".env", "w") as f:
        f.write(f"GEMINI_API_KEY={gemini_key}\n")
        f.write(f"CRYPTO_WALLET={wallet}\n")

    print(
        "\n[완료] 모든 기본 설정이 끝났습니다. 이제 이 파일을 닫고 제미나이에게 '다음'이라고 하세요."
    )


if __name__ == "__main__":
    initial_setup()
