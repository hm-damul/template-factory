# 파일명: check_key.py

import requests

key = "AIzaSyBTc3kSGWtIcJAAaXHleWFIIMFCOQmheDo"  # 방금 입력하신 키를 여기 넣었습니다.
base_url = "https://generativelanguage.googleapis.com/v1beta"


def test_models():
    print(f"🔍 키 검사 시작: {key[:10]}...")

    # 1. 사용 가능한 모델 리스트 확인
    list_url = f"{base_url}/models?key={key}"
    try:
        res = requests.get(list_url)
        if res.status_code == 200:
            models = res.json().get("models", [])
            print("✅ 사용 가능한 모델 목록:")
            for m in models:
                print(f" - {m['name']}")

            # 2. 목록 중 첫 번째 모델로 실제 테스트
            if models:
                target_model = models[0]["name"]
                print(f"\n🚀 {target_model}로 테스트 요청 중...")
                gen_url = f"{base_url}/{target_model}:generateContent?key={key}"
                payload = {"contents": [{"parts": [{"text": "hi"}]}]}
                gen_res = requests.post(gen_url, json=payload)

                if gen_res.status_code == 200:
                    print("✨ 성공! 이 키는 이제 정상 작동합니다.")
                else:
                    print(f"❌ 생성 실패: {gen_res.status_code}")
        else:
            print(f"❌ 키 자체가 유효하지 않거나 API가 비활성화됨: {res.status_code}")
            print(f"메시지: {res.text}")
    except Exception as e:
        print(f"⚠️ 연결 에러: {e}")


if __name__ == "__main__":
    test_models()
