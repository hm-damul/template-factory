# MetaPassiveIncome — MetaMask 실결제(온체인) + Fulfillment 운영 가이드

## 개요

- **결제**: 고객이 MetaMask로 네이티브 코인(ETH/MATIC 등)을 판매자 지갑으로 전송.
- **검증**: 백엔드가 RPC로 트랜잭션을 조회해 수신 주소·금액·상태를 검증한 뒤에만 주문을 PAID 처리.
- **다운로드**: PAID 후에만 일회성/제한회용 다운로드 토큰이 발급되며, `/download_token/<token>` 으로만 패키지 다운로드 가능.

## 필수 환경 변수

프로젝트 루트의 `.env` 또는 `.env.local`에 설정:

| 변수 | 설명 | 예시 |
|------|------|------|
| `MERCHANT_WALLET_ADDRESS` | **필수**. 결제 수신 지갑 주소 (EVM) | `0x1234...abcd` |
| `CHAIN_ID` | EVM 체인 ID | `1`(Ethereum), `137`(Polygon), `8453`(Base) |
| `RPC_URL` | 해당 체인 RPC URL (미설정 시 체인별 기본 공개 RPC 사용) | `https://eth.llamarpc.com` |
| `TOKEN_SYMBOL` | 표시용 코인 심볼 | `ETH`, `MATIC` |
| `PRICE_WEI` | 기본 결제 금액(wei). 상품별 report.json의 price_wei로 덮어쓰기 가능 | `10000000000000000` (0.01 ETH) |
| `DOWNLOAD_TOKEN_TTL_SECONDS` | 다운로드 토큰 유효 시간(초) | `900` (15분) |
| `DOWNLOAD_TOKEN_MAX_USES` | 토큰당 최대 다운로드 횟수 | `3` |
| `DASHBOARD_PORT` | 대시보드 서버 포트 | `8088` |

## 실행 방법

1. **환경 설정**
   ```bash
   cp .env.example .env
   # .env에서 MERCHANT_WALLET_ADDRESS, CHAIN_ID, RPC_URL, PRICE_WEI 등 수정
   ```

2. **대시보드 기동**
   ```bash
   python dashboard_server.py
   ```
   - 기본: `http://127.0.0.1:8088` (또는 `DASHBOARD_PORT` 값)

3. **제품 게시**
   - 대시보드 → Products 테이블에서 해당 제품에 **Publish** 클릭.
   - 패키지(`outputs/<product_id>/package.zip`)가 있어야 체크아웃/다운로드 가능.

## 결제·다운로드 플로우 (테스트)

1. 대시보드에서 **Checkout (Pay with MetaMask)** 링크로 체크아웃 페이지 진입.
2. **Pay with MetaMask** 클릭 → 지갑 연결 → 주문 생성 후 해당 금액으로 판매자 주소에 전송.
3. 전송 완료 후 백엔드가 자동으로 트랜잭션 해시로 검증 요청.
4. 검증 성공 시 **Download your file** 링크 표시 → 클릭 시 `/download_token/<token>` 으로 zip 다운로드.
5. 이미 결제한 tx_hash로 다시 검증 요청해도 동일 결과 반환(동일 토큰, 중복 결제 없음).

## API 요약

| 메서드 | 경로 | 용도 |
|--------|------|------|
| GET | `/checkout/<product_id>` | 체크아웃 페이지 (상품 정보 + MetaMask 결제 UI) |
| POST | `/api/payment/create_order` | 주문 생성. Body: `{ "product_id": "...", "buyer_wallet": "0x..." }` |
| POST | `/api/payment/verify` | 온체인 검증. Body: `{ "tx_hash": "0x...", "chain_id": 1, "product_id": "...", "buyer_wallet": "0x...", "order_id": "..." }` |
| GET | `/download_token/<token>` | 토큰 검증 후 패키지 zip 스트리밍 (토큰 TTL/최대 사용 횟수 적용) |

## 레저·데이터

- **주문**: `data/orders.json` — order_id, product_id, status(PENDING_PAYMENT / paid), meta(evm_tx_hash, evm_paid_at, download_token 등).
- **결제 기록**: `data/payments.json` — tx_hash, order_id, chain_id, from_wallet, to_wallet, value_wei, verified_at, verification_result(pass/fail).
- **다운로드 토큰**: `data/download_tokens.json` — 토큰별 order_id, product_id, expires_at, use_count, max_uses.
- **다운로드 로그**: `data/downloads.json` — 다운로드 이벤트(토큰, order_id, product_id, downloaded_at, ip, user_agent, count).

## 보안·운영

- 다운로드는 **반드시** 검증된 결제 후 발급된 토큰으로만 가능. `/download/<product_id>` 직접 접근은 403.
- 클라이언트가 보낸 “결제 완료” 신호만으로는 PAID 처리하지 않음. 백엔드가 RPC로 tx 검증 후에만 PAID 및 토큰 발급.
- 동일 tx_hash로 여러 주문 결제 불가(이미 사용된 tx_hash는 재검증 시 기존 주문 결과만 반환).
- 테스트용 “Mark Paid (test)”는 로컬 테스트 전용. 운영 환경에서는 `ALLOW_TEST_MARK_PAID=0` 또는 해당 버튼 비노출 권장.

## 트러블슈팅

| 현상 | 확인·조치 |
|------|------------|
| 체크아웃 페이지 404 | 해당 product_id에 대해 `outputs/<product_id>/package.zip` 존재 여부 확인. `MERCHANT_WALLET_ADDRESS` 설정 여부 확인. |
| 검증 실패 (recipient_mismatch / amount_insufficient) | 결제 시 수신 주소가 `MERCHANT_WALLET_ADDRESS`와 동일한지, 금액이 `PRICE_WEI`(또는 상품 price_wei) 이상인지 확인. 주소는 대소문자 무시. |
| RPC 오류 (rpc_request_failed / receipt_not_found) | `RPC_URL` 연결 가능 여부, 해당 체인/네트워크 일치 여부 확인. 일시 오류 시 재시도. |
| 다운로드 403 (token_expired / token_max_uses_exceeded) | 토큰 만료 또는 사용 횟수 초과. 새 결제 또는 관리자 배포용 별도 채널 사용. |
| “merchant_wallet_not_configured” | `.env`에 `MERCHANT_WALLET_ADDRESS` 설정 후 서버 재시작. |

## 요약

- **실결제만** 다운로드 허용.
- **온체인 검증** 후 PAID 처리 및 토큰 발급.
- **토큰 게이팅**으로 `/download_token/<token>` 만 패키지 제공.
- 레저(orders, payments, downloads)로 감사 및 운영 추적 가능.
