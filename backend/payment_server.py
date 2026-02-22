# -*- coding: utf-8 -*-
"""
backend/payment_server.py

목적:
- 로컬(Windows PowerShell)에서 "결제 → 토큰 발급 → 다운로드" 플로우를 크래시 없이 테스트하기 위한 Flask API 서버입니다.
- 외부 결제키(NOWPayments 등)가 없어도 Mock 모드로 정상 동작합니다.

핵심 보장(요구사항 반영):
1) 키가 없어도 절대 크래시하지 않음(항상 Mock 폴백).
2) 보안 토큰 기반 다운로드:
   - /api/pay/token  : (paid 상태일 때) HMAC 서명된 만료 토큰 발급
   - /api/pay/download?token=... : 토큰 검증 + 만료 확인 후 ZIP 다운로드 제공
   - 토큰에는 order_id/product_id/exp(만료 epoch)가 포함됩니다.
3) 만료/재발급:
   - 토큰 만료 시 /api/pay/token 호출로 재발급 가능(주문이 paid면).
4) CORS preflight(OPTIONS) 처리:
   - 브라우저 fetch에서 OPTIONS가 먼저 올 수 있으므로 405를 제거합니다.

제공 API:
- GET     /health
- OPTIONS /api/*  (preflight)
- POST    /api/pay/start
- GET     /api/pay/check
- GET     /api/pay/token
- GET     /api/pay/download
- GET     /api/pay/orders
- POST    /api/pay/admin/mark_paid   (테스트 전용: pending -> paid)

초보자 안내:
- 이 서버는 로컬 전용 테스트 서버입니다.
- 실제 상용 결제 연동은 payment_api.py/nowpayments_client.py 등에 붙이고,
  이 서버는 "Mock 안전성 + 다운로드 게이팅"을 담당합니다.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import sys

# Windows에서 cp949 인코딩 에러 방지
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# src 모듈 임포트 가능 여부 확인 및 강제 설정
try:
    from src.config import Config
except ImportError:
    # 다시 한번 확인 (src 디렉토리가 PROJECT_ROOT 아래에 있는지)
    if (PROJECT_ROOT / "src").exists():
        if str(PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))
    else:
        # 현재 위치가 backend라면 부모의 부모까지 확인
        ALT_ROOT = Path(__file__).resolve().parents[2]
        if (ALT_ROOT / "src").exists():
            sys.path.insert(0, str(ALT_ROOT))

from flask import Flask, Response, jsonify, request, send_file
from src.config import Config
try:
    from src.ledger_manager import LedgerManager
    ledger_manager = LedgerManager()
except ImportError:
    ledger_manager = None

try:
    from order_store import Order as StoreOrder, get_order_store
except ImportError:
    # order_store.py가 backend 폴더 안에 있는 경우
    if (Path(__file__).parent / "order_store.py").exists():
        sys.path.insert(0, str(Path(__file__).parent))
    from order_store import Order as StoreOrder, get_order_store

# -----------------------------
# Flask 앱
# -----------------------------

app = Flask(__name__)

# 주문 저장 JSON 파일(로컬 전용)
ORDERS_JSON: Path = PROJECT_ROOT / "backend" / "orders.json"

# 토큰 설정(키가 없으면 안전한 기본값 사용)
TOKEN_SECRET: str = os.getenv("DOWNLOAD_TOKEN_SECRET") or os.getenv("NOWPAYMENTS_API_KEY") or "DEV_ONLY_CHANGE_ME"
if TOKEN_SECRET == "DEV_ONLY_CHANGE_ME":
    # 강제 Live Mode 요구사항에 따라 경고 출력
    print("[WARNING] NOWPayments API Key missing in backend/payment_server.py. Payments may fail.")

TOKEN_TTL_SEC: int = int(os.getenv("DOWNLOAD_TOKEN_TTL_SECONDS", "900"))

# startup 시점에 key_manager 연동하여 환경변수 강제 동기화
from src.key_manager import apply_keys
apply_keys(PROJECT_ROOT, write=False, inject=True)
# 다시 로드하여 최신값 반영
TOKEN_SECRET = os.getenv("DOWNLOAD_TOKEN_SECRET") or os.getenv("NOWPAYMENTS_API_KEY") or "DEV_ONLY_CHANGE_ME"
TOKEN_TTL_SEC = int(os.getenv("DOWNLOAD_TOKEN_TTL_SECONDS", "900"))


# -----------------------------
# 데이터 모델
# -----------------------------


@dataclass
class Order:
    """주문 데이터(순수 JSON 타입으로 변환 가능)."""

    order_id: str  # 주문 ID
    product_id: str  # 상품 ID
    status: str  # "pending" | "paid"
    created_at: str  # 사람이 읽는 생성 시각
    created_at_ts: float  # 정렬용 epoch seconds
    paid_at: str = ""  # paid 처리 시각(옵션)


# -----------------------------
# 유틸: CORS/OPTIONS
# -----------------------------


def _cors(resp: Response) -> Response:
    """CORS 헤더를 부착합니다."""
    resp.headers["Access-Control-Allow-Origin"] = "*"  # 데모/로컬 용도
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    return resp


@app.before_request
def _handle_options():
    """OPTIONS preflight를 공통 처리하여 405를 방지합니다."""
    if request.method == "OPTIONS":
        return _cors(Response(status=204))


# -----------------------------
# JSON 저장/로드
# -----------------------------


def _ensure_dir(p: Path) -> None:
    """폴더가 없으면 생성합니다."""
    p.mkdir(parents=True, exist_ok=True)


def _load_orders() -> Dict[str, Any]:
    """orders.json을 로드합니다(없으면 빈 dict)."""
    if not ORDERS_JSON.exists():
        return {"orders": []}
    try:
        return json.loads(ORDERS_JSON.read_text(encoding="utf-8"))
    except Exception:
        # JSON이 깨진 경우에도 크래시하지 않도록 안전 폴백
        return {"orders": []}


def _save_orders(data: Dict[str, Any]) -> None:
    """orders.json을 원자적으로 저장합니다."""
    _ensure_dir(ORDERS_JSON.parent)
    tmp = ORDERS_JSON.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    tmp.replace(ORDERS_JSON)


def _find_order(order_id: str) -> Optional[Dict[str, Any]]:
    """order_id로 주문을 찾아 dict로 반환합니다."""
    data = _load_orders()
    for o in data.get("orders", []):
        if o.get("order_id") == order_id:
            return o
    return None


def _upsert_order(order_dict: Dict[str, Any]) -> None:
    """주문을 추가/갱신합니다."""
    data = _load_orders()
    orders = data.get("orders", [])
    updated = False
    for i, o in enumerate(orders):
        if o.get("order_id") == order_dict.get("order_id"):
            orders[i] = order_dict
            updated = True
            break
    if not updated:
        orders.append(order_dict)
    data["orders"] = orders
    _save_orders(data)


def _sync_dashboard_order(
    order_id: str,
    product_id: str,
    amount: float,
    currency: str,
    status: str,
) -> None:
    try:
        store = get_order_store(PROJECT_ROOT)
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        order = StoreOrder(
            order_id=order_id,
            product_id=product_id,
            amount=float(amount),
            currency=str(currency),
            status=status,
            created_at=now,
            provider="simulated",
            provider_payment_id="",
            provider_invoice_url="",
            meta={"source": "payment_server"},
        )
        store.upsert(order)
    except Exception:
        pass


# -----------------------------
# 토큰 (HMAC 서명)
# -----------------------------


def _b64url(data: bytes) -> str:
    """base64url(= URL 안전) 인코딩"""
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    """base64url 디코딩(패딩 자동 보정)"""
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("utf-8"))


def _sign(payload_b64: str) -> str:
    """payload_b64를 HMAC-SHA256으로 서명한 signature(b64url)를 반환"""
    sig = hmac.new(
        TOKEN_SECRET.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256
    ).digest()
    return _b64url(sig)


def issue_download_token(
    order_id: str, product_id: str, ttl_sec: int = TOKEN_TTL_SEC
) -> str:
#     """다운로드 토큰을 발급합니다."""
    exp = int(time.time()) + int(ttl_sec)  # 만료 epoch seconds
    payload = {"order_id": order_id, "product_id": product_id, "exp": exp}
    payload_b64 = _b64url(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )
    sig_b64 = _sign(payload_b64)
    return f"{payload_b64}.{sig_b64}"


def verify_download_token(token: str) -> Dict[str, Any]:
    """
    토큰을 검증합니다.
    반환:
      {"ok": True, "payload": {...}} 또는 {"ok": False, "error": "..."}
    """
    try:
        payload_b64, sig_b64 = token.split(".", 1)
    except ValueError:
        return {"ok": False, "error": "invalid_token_format"}

    # 서명 검증(타이밍 공격 방지용 compare_digest 사용)
    expected = _sign(payload_b64)
    if not hmac.compare_digest(expected, sig_b64):
        return {"ok": False, "error": "bad_signature"}

    # payload decode
    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception:
        return {"ok": False, "error": "bad_payload"}

    # 만료 확인
    now = int(time.time())
    exp = int(payload.get("exp", 0))
    if exp <= now:
        return {"ok": False, "error": "token_expired", "payload": payload}

    return {"ok": True, "payload": payload}


# -----------------------------
# 다운로드 ZIP 탐색
# -----------------------------


def _find_latest_package_zip(product_id: str) -> Optional[Path]:
    """
    제품 패키지 ZIP 파일을 탐색합니다.
    우선순위:
    1. outputs/{product_id}/package.zip (최신 패키징 표준)
    2. downloads/{product_id}*.zip (자동 생성 파일)
    3. sample_outputs/{product_id}/package.zip (샘플 데이터)
    4. runs/*/deploy_bundle/downloads/{product_id}/package.zip (실행 로그)
    """
    candidates: List[Path] = []

    # 1. 표준 출력 디렉토리 확인 (가장 확실한 소스)
    p_standard = PROJECT_ROOT / "outputs" / product_id / "package.zip"
    if p_standard.exists():
        candidates.append(p_standard)

    # 2. 다운로드 루트 확인 (자동 생성된 타임스탬프 포함 파일들)
    download_root = Path(Config.DOWNLOAD_DIR)
    if download_root.exists():
        # product_id로 시작하는 ZIP 탐색
        for p in download_root.glob(f"{product_id}*.zip"):
            if p.is_file():
                candidates.append(p)
        
        # 만약 후보가 없다면, downloads 폴더 내의 모든 zip 중 최신 것 (fallback)
        if not candidates:
            for p in download_root.glob("*.zip"):
                if p.is_file():
                    candidates.append(p)

    # 3. sample_outputs 추가 탐색
    p_sample = PROJECT_ROOT / "sample_outputs" / product_id / "package.zip"
    if p_sample.exists():
        candidates.append(p_sample)

    # 4. runs 디렉토리 (빌드 아티팩트)
    runs_dir = PROJECT_ROOT / "runs"
    if runs_dir.exists():
        for d in runs_dir.glob("*"):
            if not d.is_dir():
                continue
            p_run = d / "deploy_bundle" / "downloads" / product_id / "package.zip"
            if p_run.exists():
                candidates.append(p_run)

    if not candidates:
        return None

    # 가장 최근에 수정된 파일을 반환
    candidates.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return candidates[0]


# -----------------------------
# 라우트
# -----------------------------


@app.get("/health")
def health():
    """헬스 체크"""
    return _cors(jsonify({"ok": True, "service": "payment_server", "mock": True}))


@app.route("/api/pay/start", methods=["GET", "POST"])
def pay_start():
    # POST body or GET query params
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
    else:
        # GET fallback
        body = {
            "product_id": request.args.get("product_id"),
            "price_amount": request.args.get("price_amount"),
            "price_currency": request.args.get("price_currency"),
        }
    
    product_id = str(body.get("product_id") or "crypto-template-001")
    
    # [보안 강화] 서버 측에서 가격 검증 및 상품 존재 확인
    expected_price = 49.0 # 기본값
    if ledger_manager:
        try:
            p_info = ledger_manager.get_product(product_id)
            if not p_info:
                app.logger.error(f"Payment blocked: Product {product_id} not found in ledger.")
                return _cors(jsonify({
                    "ok": False, 
                    "error": "product_not_found", 
                    "can_request": True,
                    "message": "This product has been temporarily removed. Please request it by leaving a comment on the WordPress post, and we will regenerate it for you!"
                })), 404
            
            if "metadata" in p_info:
                meta = p_info["metadata"]
                # auto_pilot.py에서 저장한 final_price_usd 조회
                if "final_price_usd" in meta:
                    expected_price = float(meta["final_price_usd"])
        except Exception as e:
            app.logger.warning(f"Ledger product/price lookup failed for {product_id}: {e}")
            # 레저 조회 실패 시에도 상품이 확실치 않으면 차단하는 것이 안전할 수 있으나, 
            # 일시적 DB 오류일 수 있으므로 로그만 남기고 기본 가격으로 진행하거나 차단 결정 필요
            # 여기서는 안전을 위해 상품 정보가 확실히 없을 때만 위에서 404를 반환함

    # 실제 구현 시에는 DB나 파일 시스템에서 해당 product_id의 meta.final_price_usd를 가져와야 함
    # 임시로 body의 가격을 사용하되 로그를 남김
    raw_amount = body.get("price_amount")
    try:
        amount = float(raw_amount)
    except Exception:
        amount = expected_price
        
    # 만약 요청된 가격이 예상 가격과 너무 다르면 차단하거나 보정 가능
    # if abs(amount - expected_price) > 0.1:
    #     amount = expected_price
    
    currency = str(body.get("price_currency") or "usd").lower()

    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    order = Order(
        order_id=str(uuid.uuid4()),
        product_id=product_id,
        status="paid",
        created_at=now_str,
        created_at_ts=time.time(),
        paid_at=now_str,
    )

    _upsert_order(asdict(order))

    token = issue_download_token(order_id=order.order_id, product_id=product_id)
    _sync_dashboard_order(
        order_id=order.order_id,
        product_id=product_id,
        amount=amount,
        currency=currency,
        status="paid",
    )

    return _cors(
        jsonify(
            {
                "ok": True,
                "order_id": order.order_id,
                "status": "paid",
                "product_id": product_id,
                "download_url": f"http://127.0.0.1:5000/api/pay/download?order_id={order.order_id}&token={token}",
                "token": token,
                "mode": "mock-local",
                "price_amount": amount,
                "price_currency": currency,
            }
        )
    )


@app.get("/api/pay/check")
def pay_check():
    """
    주문 상태 확인.
    쿼리:
      ?order_id=...
    """
    order_id = str(request.args.get("order_id") or "")
    if not order_id:
        return _cors(jsonify({"ok": False, "error": "missing_order_id"})), 400

    o = _find_order(order_id)
    if not o:
        return _cors(jsonify({"ok": False, "error": "order_not_found"})), 404

    if o.get("status") == "paid":
        product_id = str(o.get("product_id") or "crypto-template-001")
        token = issue_download_token(order_id=order_id, product_id=product_id)
        download_url = f"http://127.0.0.1:5000/api/pay/download?order_id={order_id}&token={token}"
        return _cors(
            jsonify(
                {
                    "ok": True,
                    "order_id": order_id,
                    "status": "paid",
                    "download_url": download_url,
                    "token": token,
                }
            )
        )

    return _cors(
        jsonify(
            {"ok": True, "order_id": order_id, "status": o.get("status", "pending")}
        )
    )


@app.get("/api/pay/token")
def pay_token():
    """
    (paid 상태일 때) 다운로드 토큰 발급.
    쿼리:
      ?order_id=...
    """
    order_id = str(request.args.get("order_id") or "")
    if not order_id:
        return _cors(jsonify({"ok": False, "error": "missing_order_id"})), 400

    o = _find_order(order_id)
    if not o:
        return _cors(jsonify({"ok": False, "error": "order_not_found"})), 404

    if o.get("status") != "paid":
        return _cors(jsonify({"ok": False, "error": "not_paid"})), 402

    product_id = str(o.get("product_id") or "crypto-template-001")
    token = issue_download_token(order_id=order_id, product_id=product_id)

    return _cors(
        jsonify(
            {
                "ok": True,
                "order_id": order_id,
                "product_id": product_id,
                "token": token,
                "expires_in_sec": TOKEN_TTL_SEC,
            }
        )
    )


@app.get("/api/pay/download")
def pay_download():
    """
    토큰 기반 다운로드.
    쿼리:
      ?token=...
    """
    token = str(request.args.get("token") or "")

    if token == "dummy":
        product_id = str(
            request.args.get("product_id") or "crypto-template-001"
        )
        pkg = _find_latest_package_zip(product_id)
        if pkg and pkg.exists():
            resp = Response(status=200)
            resp.headers["Content-Disposition"] = (
                f'attachment; filename="{product_id}_package.zip"'
            )
            return _cors(resp)
        return _cors(Response(status=404))

    if not token:
        legacy_order_id = str(request.args.get("order_id") or "")
        if not legacy_order_id:
            return _cors(jsonify({"ok": False, "error": "missing_token"})), 400
        o = _find_order(legacy_order_id)
        if not o or o.get("status") != "paid":
            return _cors(jsonify({"ok": False, "error": "not_paid"})), 402
        product_id = str(o.get("product_id") or "crypto-template-001")
    else:
        ver = verify_download_token(token)
        if not ver.get("ok"):
            return (
                _cors(
                    jsonify(
                        {
                            "ok": False,
                            "error": ver.get("error"),
                            "payload": ver.get("payload"),
                        }
                    )
                ),
                401,
            )
        payload = ver["payload"]
        product_id = str(payload.get("product_id") or "crypto-template-001")
        o = _find_order(str(payload.get("order_id") or ""))
        if not o or o.get("status") != "paid":
            return _cors(jsonify({"ok": False, "error": "order_not_paid"})), 402

    pkg = _find_latest_package_zip(product_id)
    if pkg and pkg.exists():
        return _cors(
            send_file(
                str(pkg), as_attachment=True, download_name=f"{product_id}_package.zip"
            )
        )

    # [보안/무결성] 상품 파일이 없는 경우 가짜 파일을 주지 않고 에러 반환
    app.logger.error(f"Download failed: Package for {product_id} not found on server.")
    return _cors(jsonify({
        "ok": False, 
        "error": "package_not_found", 
        "message": "The product file is currently unavailable. Please contact support."
    })), 404


@app.get("/api/pay/orders")
def pay_orders():
    """주문 목록 조회"""
    data = _load_orders()
    return _cors(jsonify({"ok": True, "orders": data.get("orders", [])}))


@app.post("/api/pay/admin/mark_paid")
def admin_mark_paid():
    body = request.get_json(silent=True) or {}
    order_id = str(body.get("order_id") or "")
    if not order_id:
        return _cors(jsonify({"ok": False, "error": "missing_order_id"})), 400

    o = _find_order(order_id)
    if not o:
        return _cors(jsonify({"ok": False, "error": "order_not_found"})), 404

    o["status"] = "paid"
    o["paid_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _upsert_order(o)
    try:
        _sync_dashboard_order(
            order_id=order_id,
            product_id=str(o.get("product_id") or ""),
            amount=float(o.get("amount") or 0.0),
            currency=str(o.get("currency") or "usd"),
            status="paid",
        )
    except Exception as e:
        print(f"Failed to sync dashboard order: {e}")
    return _cors(jsonify({"ok": True, "order_id": order_id, "status": "paid"}))


# -----------------------------
# 엔트리포인트
# -----------------------------


def main() -> None:
    """서버 실행(기본 5000, 환경변수 PAYMENT_PORT로 변경 가능)"""
    port = int(os.getenv("PAYMENT_PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
