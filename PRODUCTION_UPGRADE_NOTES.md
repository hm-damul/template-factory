# MetaPassiveIncome — Production Upgrade Notes (2026-02-02)

이 파일은 **새 채팅창에서 이어 개발**할 때 필요한 핵심 요약/경로/실행 커맨드를 담습니다.

## 1) 이번 업그레이드 핵심
- **PremiumProduct 콘텐츠 엔진(premium_content_engine)** 기반으로 product.md를 “유료 전자책 수준” 구조로 생성
- **상업용 PDF 레이아웃(pro_pdf_engine)**: 커버/TOC/헤더·푸터/콜아웃/코드블록/표/리스트 지원
- **보너스 패키지 강화(premium_bonus_generator)**: KPI 트래커, 세일즈페이지/오퍼 템플릿, 고객지원 매크로 등 추가
- **프로모션 공장(promotion_factory)**: 블로그 장문/인스타/숏폼/세일즈페이지 카피를 고정 파일명으로 생성
- **결제 게이팅 강화(payment_api + api/pay/download)**:
  - 정적 downloads/outputs 경로 노출 최소화
  - HMAC 서명 토큰 + 만료 + **jti(1회용) 사용 기록**(저장소 지원 시)
- **product_history.jsonl 누적 로그**: data/product_history.jsonl

## 2) 변경된 주요 파일
- MetaPassiveIncome_FINAL/auto_pilot.py
- MetaPassiveIncome_FINAL/pro_pdf_engine.py
- MetaPassiveIncome_FINAL/promotion_factory.py
- MetaPassiveIncome_FINAL/premium_bonus_generator.py
- MetaPassiveIncome_FINAL/order_store.py
- MetaPassiveIncome_FINAL/payment_api.py
- MetaPassiveIncome_FINAL/api/_security.py
- MetaPassiveIncome_FINAL/api/download.py
- MetaPassiveIncome_FINAL/api/pay/start.py
- MetaPassiveIncome_FINAL/api/pay/check.py
- MetaPassiveIncome_FINAL/api/pay/download.py
- MetaPassiveIncome_FINAL/vercel.json

## 3) 로컬 운영 실행(Windows / Cursor)
### (A) 제품 생성(자동)
1) Cursor에서 프로젝트 폴더 열기
2) 터미널(PowerShell)에서:
   python auto_pilot.py --batch 1

생성물:
- outputs/<product_id>/product.md, product_en.pdf, bonus_ko.zip, promotions/*, package.zip

### (B) 대시보드/스케줄러
- dashboard_server.py / auto_mode_daemon.py를 그대로 사용
- 자동 생성은 auto_pilot.py를 호출하도록 되어있음

### (C) 결제 게이트(로컬)
- backend/payment_server.py는 기존 mock 서버(호환 유지)
- “운영용 게이트 로직”은 payment_api.py가 담당

## 4) 배포(Vercel) 핵심
- vercel.json에서 downloads/outputs 정적 서빙을 제거
- 다운로드는 **/api/pay/download?order_id=...&token=...** 로만 제공

운영에서 권장 환경변수:
- DOWNLOAD_TOKEN_SECRET (필수급)
- NOWPAYMENTS_API_KEY (실결제)
- UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN (토큰 1회 사용 기록/주문 저장)

## 5) 다음 작업(우선순위)
1) 실제 판매 사이트(landing + checkout)에서 API 연동(START→CHECK→DOWNLOAD)
2) Upstash 붙여서 serverless에서도 order/token 상태 영속화
3) 프로모션 webhook/자동 포스팅(플랫폼 정책 준수 범위 내) 확장
