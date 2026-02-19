def create_env_file():
    print("=== CATP Project Setup ===")
    config = {
        "GEMINI_API_KEY": input("Gemini API Key를 입력하세요: "),
        "CRYPTO_WALLET_ADDRESS": input("결제받을 암호화폐 지갑 주소를 입력하세요: "),
        "VERCEL_TOKEN": input("Vercel Deploy Token을 입력하세요 (선택사항): "),
        "SUPABASE_URL": input("Supabase URL을 입력하세요: "),
        "SUPABASE_KEY": input("Supabase Anon Key를 입력하세요: "),
        "PINTEREST_ACCESS_TOKEN": input("Pinterest API Token을 입력하세요: "),
    }

    with open(".env", "w") as f:
        for key, value in config.items():
            f.write(f"{key}={value}\n")
    print("\n[성공] .env 파일이 생성되었습니다. 이제 복사·붙여넣기를 계속 진행하세요.")


if __name__ == "__main__":
    create_env_file()
