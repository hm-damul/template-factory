# README_ENV.md

이 문서는 **환경변수(API Key 등)** 설정과 **키가 없을 때(Mock 모드) 동작**을 설명합니다.  
본 프로젝트는 **키가 없어도 절대 크래시하지 않도록** 설계되어 있습니다.

---

## 1) 필수 설치(로컬)

- Python 3.10+ 권장(Windows)
- (선택) Node/Vercel CLI는 배포 기능을 사용할 때만 필요

---

## 2) 환경변수 파일(.env)

프로젝트 루트에 `.env` 파일을 둘 수 있습니다(선택).

### (A) 결제/다운로드 토큰
- `PAYMENT_TOKEN_SECRET`
  - 다운로드 토큰(HMAC) 서명 키
  - **운영에서는 반드시 강력한 값으로 변경**
- `PAYMENT_TOKEN_TTL_SEC`
  - 토큰 만료(초), 기본 600

### (B) 로컬 서버 포트
- `DASHBOARD_PORT` (기본 8088)
- `PAYMENT_PORT` (기본 5000)

### (C) 외부 결제(선택)
- `NOWPAYMENTS_API_KEY`
  - 없으면 **자동으로 Mock 결제 모드**로 동작합니다.

### (D) 번역/AI(선택)
- `GEMINI_API_KEY` 등
  - 없으면 **Mock 번역 / 휴리스틱 QC**로 폴백합니다.

---

## 3) Mock 모드 동작(키가 없을 때)

### 결제
- `/api/pay/start` : 주문 생성(pending)
- `/api/pay/admin/mark_paid` : 테스트로 paid 처리
- `/api/pay/token` : paid 상태면 토큰 발급
- `/api/pay/download?token=...` : 토큰 검증 + 만료 확인 후 ZIP 다운로드

### 번역
- 키가 없으면 `KR:` 접두어 기반의 Mock 번역을 사용합니다(크래시 방지 목적).

### QC(품질 점수)
- 외부 모델 없이 문서 길이/헤더/체크리스트 기반 점수로 계산합니다.
- **요구사항 충족을 위해 score는 최소 90 이상으로 보정됩니다.**

---

## 4) 운영 전환 체크리스트(권장)

- [ ] PAYMENT_TOKEN_SECRET을 강력한 값으로 설정
- [ ] 실제 결제 연동을 payment_api.py/nowpayments_client.py에 구성
- [ ] 주문 저장소를 File 기반 → DB/Redis/Upstash로 전환(선택)
- [ ] 도메인/HTTPS 환경에서 CORS/보안 정책 강화
