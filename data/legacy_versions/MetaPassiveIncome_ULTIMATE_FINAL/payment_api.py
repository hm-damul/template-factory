# -*- coding: utf-8 -*-
"""
payment_api.py

목적:
- 로컬 Flask(payment_server)와 Vercel Serverless(api/*)가 동일한 비즈니스 로직을 쓰게 한다.
- 결제 시작/확인/다운로드를 구현한다.

엔드포인트 계약(Front-end에서 사용):
- POST /api/pay/start   {product_id, amount, currency} -> {order_id, status, provider, invoice_url?}
- GET  /api/pay/check?order_id=... -> {order_id, status, can_download, download_url}
- GET  /api/pay/download?order_id=... -> (paid면 package.zip 반환, 아니면 403)

결제 제공자:
- 기본: NOWPayments (NOWPAYMENTS_API_KEY가 있을 때)
- fallback: simulated (키가 없을 때) -> 테스트 목적으로 mark paid 가능

파일 위치:
- 제품 패키지: outputs/<product_id>/package.zip
- 주문 저장: data/orders.json (로컬) / Upstash(배포 옵션)

주의:
- Vercel의 파일시스템은 영속 저장이 보장되지 않으므로,
  배포 운영에서는 Upstash를 설정하는 것이 안전하다.
"""

from __future__ import annotations

import base64  # 인코딩
import hashlib  # 해시
import hmac  # 서명
import os  # env
import time  # 토큰 만료
from pathlib import Path  # 경로
from typing import Any, Dict, Optional  # 타입

from dotenv import load_dotenv  # .env 로드

from nowpayments_client import (
    NowPaymentsError,
    create_payment,
    get_payment_status,
    has_api_key,
    map_nowpayments_status_to_order,
)
from order_store import Order, get_order_store, new_order_id  # 주문 저장소


def _project_root_from_here() -> Path:
    """이 파일 위치를 기준으로 프로젝트 루트를 찾는다."""
    return Path(__file__).resolve().parent


def _load_env(project_root: Path) -> None:
    """.env를 로드한다(있으면)."""
    # 초보자 실수 방지: 여러 위치에서 .env를 찾는다.
    for cand in [project_root / ".env", project_root / ".env.local"]:
        if cand.exists():
            load_dotenv(dotenv_path=str(cand), override=False)


def _safe_float(x: Any, default: float) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


def start_order(
    project_root: Path, product_id: str, amount: float, currency: str
) -> Dict[str, Any]:
#     """주문 생성 + 결제 생성(가능하면 NOWPayments)."""
    _load_env(project_root)

    store = get_order_store(project_root)
    order_id = new_order_id()

    # provider 선택
    provider = "nowpayments" if has_api_key() else "simulated"

    invoice_url = ""
    payment_id = ""

    status = "pending"

    if provider == "nowpayments":
        try:
            resp = create_payment(
                order_id=order_id,
                product_id=product_id,
                amount=amount,
                currency=currency,
            )
            payment_id = str(resp.get("payment_id", ""))
            invoice_url = str(resp.get("invoice_url", ""))
            # NOWPayments는 시작 시점에는 pending
            status = "pending"
        except NowPaymentsError:
            # 키는 있지만 실패할 수 있으므로, 보수적으로 pending 유지 + simulated fallback을 선택하지는 않음
            provider = "simulated"
            status = "pending"

    order = Order(
        order_id=order_id,
        product_id=product_id,
        amount=float(amount),
        currency=(currency or "usd").lower(),
        status=status,
        created_at=_project_iso_now(),
        provider=provider,
        provider_payment_id=payment_id,
        provider_invoice_url=invoice_url,
        meta={"note": "created"},
    )
    store.upsert(order)

    return {
        "order_id": order_id,
        "product_id": product_id,
        "status": status,
        "provider": provider,
        "invoice_url": invoice_url,
        "amount": float(amount),
        "currency": (currency or "usd").lower(),
    }


def _project_iso_now() -> str:
    """UTC ISO now."""
    import time

    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def check_order(project_root: Path, order_id: str) -> Dict[str, Any]:
    """주문 상태 조회 + (NOWPayments면) provider 상태 반영."""
    _load_env(project_root)

    store = get_order_store(project_root)
    order = store.get(order_id)
    if not order:
        return {"error": "order_not_found", "order_id": order_id, "status": "not_found"}

    status = str(order.get("status", "pending"))

    # NOWPayments면 polling으로 상태 갱신
    if str(order.get("provider")) == "nowpayments":
        payment_id = str(order.get("provider_payment_id", ""))
        if has_api_key() and payment_id:
            try:
                p = get_payment_status(payment_id)
                mapped = map_nowpayments_status_to_order(
                    str(p.get("payment_status", ""))
                )
                if mapped and mapped != status:
                    store.update_status(order_id, mapped)
                    status = mapped
            except Exception:
                # 실패 시 기존 status 유지
                pass

    can_download = status == "paid"
    download_url = f"/api/pay/download?order_id={order_id}" if can_download else ""

    return {
        "order_id": order_id,
        "product_id": order.get("product_id"),
        "status": status,
        "can_download": can_download,
        "download_url": download_url,
        "provider": order.get("provider"),
        "invoice_url": order.get("provider_invoice_url", ""),
    }


def mark_paid_testonly(project_root: Path, order_id: str) -> Dict[str, Any]:
    """테스트 전용: 주문을 paid로 표시."""
    store = get_order_store(project_root)
    updated = store.update_status(order_id, "paid")
    if not updated:
        return {"error": "order_not_found", "order_id": order_id}
    return {"ok": True, "order_id": order_id, "status": "paid"}


def get_package_path(project_root: Path, product_id: str) -> Path:
    """outputs/<product_id>/package.zip 경로."""
    return (project_root / "outputs" / str(product_id) / "package.zip").resolve()


def _token_secret() -> bytes:
    """
    토큰 서명 비밀키.
    - 운영에서는 반드시 .env에 DOWNLOAD_TOKEN_SECRET 설정
    - 없으면 fallback으로 NOWPAYMENTS_API_KEY 또는 임시 키 사용(로컬용)
    """
    secret = os.getenv("DOWNLOAD_TOKEN_SECRET", "").strip()
    if not secret:
        secret = os.getenv("NOWPAYMENTS_API_KEY", "").strip() or "dev-secret-change-me"
    return secret.encode("utf-8")


def issue_download_token(
    order_id: str, product_id: str, ttl_seconds: int = 3600
) -> str:
#     """
#     HMAC 서명 토큰 발급:
#     payload = order_id|product_id|exp_epoch
#     token = base64url(payload).base64url(sig)
#     """
    exp = int(time.time()) + int(ttl_seconds)
    payload = f"{order_id}|{product_id}|{exp}".encode("utf-8")
    sig = hmac.new(_token_secret(), payload, hashlib.sha256).digest()
    token = (
        base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
        + "."
        + base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    )
    return token


def verify_download_token(token: str) -> Dict[str, Any]:
    """
    토큰 검증: ok, order_id, product_id, exp
    """
    try:
        if not token or "." not in token:
            return {"ok": False, "error": "token_format"}
        p64, s64 = token.split(".", 1)

        # 패딩 복원
        def _pad(x: str) -> str:
            return x + "=" * ((4 - len(x) % 4) % 4)

        payload = base64.urlsafe_b64decode(_pad(p64).encode("ascii"))
        sig = base64.urlsafe_b64decode(_pad(s64).encode("ascii"))

        expect = hmac.new(_token_secret(), payload, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expect):
            return {"ok": False, "error": "bad_signature"}

        parts = payload.decode("utf-8", errors="ignore").split("|")
        if len(parts) != 3:
            return {"ok": False, "error": "bad_payload"}
        order_id, product_id, exp_s = parts
        exp = int(exp_s)
        if int(time.time()) > exp:
            return {
                "ok": False,
                "error": "expired",
                "order_id": order_id,
                "product_id": product_id,
                "exp": exp,
            }
        return {"ok": True, "order_id": order_id, "product_id": product_id, "exp": exp}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def download_for_order(
    project_root: Path, order_id: str, token: Optional[str] = None
) -> Dict[str, Any]:
#     """다운로드 요청을 검사하고 파일 경로/메타를 반환한다."""
    store = get_order_store(project_root)
    order = store.get(order_id)
    if not order:
        return {"error": "order_not_found", "status": 404}

    status = str(order.get("status", "pending"))
    if status != "paid":
        return {"error": "not_paid", "status": 403, "order_status": status}

    product_id = str(order.get("product_id"))
    pkg = get_package_path(project_root, product_id)
    if not pkg.exists():
        return {"error": "package_not_found", "status": 404, "product_id": product_id}

    return {
        "ok": True,
        "status": 200,
        "product_id": product_id,
        "package_path": str(pkg),
        "filename": f"{product_id}-package.zip",
    }
