# MetaPassiveIncome ULTIMATE 실행 가이드(초보자용)

## 0) 준비
- Windows 10/11
- Python 3.10+ 권장
- (선택) Vercel CLI

## 1) 가상환경 생성/활성화
PowerShell(프로젝트 루트)에서:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2) 제품 1개 생성(다국어 + PDF + 보너스)
```powershell
python auto_pilot.py --batch 1 --languages en,ko
```

생성 결과:
- outputs/<product_id>/product.md
- outputs/<product_id>/product_ko.md
- outputs/<product_id>/product_en.pdf / product_ko.pdf
- outputs/<product_id>/bonus_ko.zip 등

## 3) 대시보드
```powershell
python dashboard_server.py
```
접속:
- http://127.0.0.1:8088/ultimate

## 4) 로컬 결제 서버
```powershell
python backend/payment_server.py
```

## 5) SNS 자동 포스팅(모의 모드)
기본은 mock 모드입니다(키 없으면 안전).

- 실제 X 사용 시: 환경변수 `X_BEARER_TOKEN` 필요
- mock 강제: `SOCIAL_MOCK=1`


## 빠른 자동 점검(권장)

### 터미널에 붙여넣기(PowerShell)
```powershell
# 프로젝트 루트로 이동
cd D:\MetaPassiveIncome_FINAL\MetaPassiveIncome_FINAL

# 가상환경 생성/활성화(최초 1회)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 의존성 설치(최초 1회)
pip install -r requirements.txt

# 필수 기능 자동 테스트 실행
python tools\self_test.py
```

- TEST 1: 상품 생성(마크다운/PDF/보너스/프로모션) 생성 확인
- TEST 2: 대시보드 서버(/health, /ultimate) 확인
- TEST 3: 결제 Mock 플로우(토큰 발급 + 다운로드) 확인
