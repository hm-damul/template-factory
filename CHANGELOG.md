# CHANGELOG.md

## MetaPassiveIncome_FINAL (Unified)

### Merge Summary
- 6개 ZIP을 병합하여 하나의 실행 가능한 통합 버전으로 구성:
  - MetaPassiveIncome_ULTIMATE_FINAL.zip
  - MetaPassiveIncome_PREMIUM_ALL_INTEGRATED.zip
  - MetaPassiveIncome_FULL_AUTOMATION_PROMO_PATCHED.zip
  - MetaPassiveIncome_PATCHED (1).zip
  - MetaPassiveIncome_FIXED.zip
  - MetaPassiveIncome_FIXED_PATCHED.zip

### Conflict Handling
- 동일 경로 충돌 파일은 단순 덮어쓰지 않고, 완성도/기능 키워드/결제·대시보드 우선순위 기반으로 선택.
- 선택되지 않은 버전은 `data/legacy_versions/<zipname>/...`에 보관.

### Hardening / Fixes
- (Payment) backend/payment_server.py:
  - 토큰(HMAC) 기반 다운로드 게이팅 구현
  - 만료/재발급(/api/pay/token) + 다운로드(/api/pay/download?token=...)
  - OPTIONS/CORS preflight 처리로 405 제거
  - 키 없는 환경에서도 Mock 안전 동작 보장
- (Dashboard) dashboard_server.py:
  - 라우트가 app.run() 이후에 있던 문제 수정(등록 순서 보장)
  - /health 추가
  - 기본 포트 8088로 조정
- (Auto Pilot) auto_pilot.py:
  - 요구 테스트용 CLI 추가: --batch, --languages
  - product.md / quality_report.json / product_en.pdf / product_ko.pdf / bonus_ko.zip / promotions 생성 보장
  - 기존 auto_pilot은 auto_pilot_legacy.py로 보존하여 하위호환 유지
- (Testing) tools/self_test.py:
  - TEST1~3 자동 검증 스크립트 추가

### Notes
- outputs/, runs/, __pycache__, .venv 등 캐시/산출물/가상환경 폴더는 최종 ZIP에서 제외.
- API 키가 없으면 Mock 모드로 자동 폴백하도록 설계(크래시 금지).
