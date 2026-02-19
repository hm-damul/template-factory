# -*- coding: utf-8 -*-
"""
payment_api.py

목적(운영용 공통 로직):
- 로컬 Flask(payment_server)와 Vercel Serverless(api/*)가 동일한 결제/게이팅 로직을 공유하도록 한다.
- 결제 시작/확인/다운로드 게이트(토큰) 기능을 제공한다.

엔드포인트 계약(Front-end에서 사용):
- POST /api/pay/start   {product_id, amount, currency} -> {order_id, status, provider, invoice_url?}
- GET  /api/pay/check?order_id=... -> {order_id, status, can_download, download_url, token?}
- GET  /api/pay/download?order_id=...&token=... -> (paid면 package.zip 반환, 아니면 403)

결제 제공자:
- 기본: NOWPayments (NOWPAYMENTS_API_KEY가 있을 때)
- fallback: simulated (키가 없을 때) -> 운영 전환 시에도 안전(실제 결제 없이도 파일은 생성되지만, 다운로드 게이트는 유지)

보안(핵심):
- 다운로드는 반드시 서버가 발급한 '서명 토큰'이 필요하다.
- 토큰은 짧은 TTL(기본 15분) + 선택적 1회 사용(jti) 방지.
- download 요청 시:
  1) token 서명/만료 검증
  2) order_id/product_id 일치 검증
  3) order.status == paid/delivered 재검증
  4) jti 1회 사용 체크(저장소 지원 시) + 기록(consume)

파일 위치:
- 제품 패키지: outputs/<product_id>/package.zip
- 주문 저장: data/orders.json (로컬) / Upstash(배포 옵션)

운영 권장:
- 배포 운영(서버리스)에서는 Upstash를 반드시 설정하여 주문/토큰 재사용 방지를 확보한다.
"""

from __future__ import annotations

import base64  # token encoding
import hashlib  # token secret / HMAC
import hmac  # token signature
import os  # env
import re
import secrets  # jti
import time  # expiry
from pathlib import Path  # paths
from typing import Any, Dict, Optional  # types

from dotenv import load_dotenv  # .env 로드

from nowpayments_client import (
    NowPaymentsError,
    create_payment,
    get_payment_status,
    has_api_key,
    map_nowpayments_status_to_order,
)
from order_store import Order, get_order_store, new_order_id  # 주문 저장소
from evm_verifier import verify_evm_payment as evm_verify_on_chain  # 온체인 검증

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# -----------------------------
# Paths / env
# -----------------------------


def _project_root_from_here() -> Path:
    """이 파일 위치를 기준으로 프로젝트 루트를 찾는다."""
    return Path(__file__).resolve().parent


def _load_env(project_root: Path) -> None:
    """.env를 로드한다(있으면)."""
    for cand in [project_root / ".env", project_root / ".env.local"]:
        if cand.exists():
            load_dotenv(dotenv_path=str(cand), override=False)


# -----------------------------
# Token helpers (HMAC, no jwt dependency)
# -----------------------------


def _token_secret(project_root: Path) -> bytes:
    """다운로드 토큰 서명용 secret를 반환한다.

    우선순위:
    1) DOWNLOAD_TOKEN_SECRET (권장)
    2) NOWPAYMENTS_API_KEY
    3) 프로젝트 경로 기반 fallback (운영에서는 1/2를 반드시 설정)
    """
    s = (
        os.getenv("DOWNLOAD_TOKEN_SECRET")
        or os.getenv("NOWPAYMENTS_API_KEY")
        or str(project_root)
    )
    return hashlib.sha256(str(s).encode("utf-8")).digest()


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("ascii"))


def issue_download_token(
    project_root: Path,
    *,
    order_id: str,
    product_id: str,
    ttl_seconds: int = 900,
    one_time: bool = True,
) -> str:
#     """서명된 다운로드 토큰 발급(HMAC).
# 
#     포맷(문자열):
#       base64url(order_id|product_id|exp|jti|one_time|sig_b64)
# 
#     - jti: 랜덤 토큰 ID(재사용 방지 키)
#     - one_time: "1"이면 저장소가 지원하는 한 1회 사용 강제
#     - sig = HMAC_SHA256(secret, order_id|product_id|exp|jti|one_time)
#     """
    exp = int(time.time()) + int(ttl_seconds)
    jti = secrets.token_hex(8)
    one = "1" if bool(one_time) else "0"
    msg = f"{order_id}|{product_id}|{exp}|{jti}|{one}".encode("utf-8")
    sig = hmac.new(_token_secret(project_root), msg, hashlib.sha256).digest()
    token = _b64url(msg + b"|" + _b64url(sig).encode("ascii"))
    return token


def verify_download_token(project_root: Path, token: str) -> Dict[str, Any]:
    """토큰 검증. 성공 시 {ok, order_id, product_id, exp, jti, one_time} 반환."""
    try:
        raw = _b64url_decode(token)
        parts = raw.split(b"|")
        if len(parts) < 6:
            return {"ok": False, "error": "bad_token_format"}

        order_id = parts[0].decode("utf-8")
        product_id = parts[1].decode("utf-8")
        exp = int(parts[2].decode("utf-8"))
        jti = parts[3].decode("utf-8")
        one_time = parts[4].decode("utf-8")
        sig_b64 = parts[5].decode("utf-8")

        msg = f"{order_id}|{product_id}|{exp}|{jti}|{one_time}".encode("utf-8")
        expected = hmac.new(_token_secret(project_root), msg, hashlib.sha256).digest()
        got = _b64url_decode(sig_b64)

        if not hmac.compare_digest(expected, got):
            return {"ok": False, "error": "bad_signature"}
        if int(time.time()) > exp:
            return {"ok": False, "error": "token_expired", "exp": exp}

        return {
            "ok": True,
            "order_id": order_id,
            "product_id": product_id,
            "exp": exp,
            "jti": jti,
            "one_time": one_time == "1",
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def consume_token_if_needed(
    project_root: Path, *, order_id: str, jti: str, one_time: bool
) -> Dict[str, Any]:
#     """1회용 토큰이면 사용 기록/중복 차단."""
    store = get_order_store(project_root)

    if not one_time:
        return {"ok": True, "consumed": False}

    # 저장소가 used 체크를 지원하지 않는 경우(최소 호환)
    if not hasattr(store, "is_download_jti_used") or not hasattr(
        store, "mark_download_jti_used"
    ):
        return {"ok": True, "consumed": False, "warning": "store_has_no_jti_tracking"}

    if bool(store.is_download_jti_used(order_id, jti)):  # type: ignore[attr-defined]
        return {"ok": False, "error": "token_already_used"}

    store.mark_download_jti_used(order_id, jti)  # type: ignore[attr-defined]
    return {"ok": True, "consumed": True}


# -----------------------------
# Product package helpers
# -----------------------------


def get_package_path(project_root: Path, product_id: str) -> Path:
    """outputs/<product_id>/package.zip 경로. Vercel에서는 루트의 package.zip 가능성도 체크."""
    # 1) 로컬 구조: outputs/<product_id>/package.zip
    p1 = (project_root / "outputs" / str(product_id) / "package.zip").resolve()
    if p1.exists():
        return p1
    
    # 2) Vercel 배포 구조: 루트에 바로 package.zip이 있는 경우 (Publisher가 그렇게 업로드함)
    p2 = (project_root / "package.zip").resolve()
    if p2.exists():
        return p2
        
    return p1


# -----------------------------
# EVM 결제 레저 (payments.json, downloads.json, download_tokens.json)
# -----------------------------

def _is_vercel() -> bool:
    """Vercel 환경인지 확인."""
    return os.getenv("VERCEL") == "1" or "NOW_REGION" in os.environ


def _payments_path(project_root: Path) -> Path:
    return project_root / "data" / "payments.json"


def _downloads_path(project_root: Path) -> Path:
    return project_root / "data" / "downloads.json"


def _download_tokens_path(project_root: Path) -> Path:
    return project_root / "data" / "download_tokens.json"


def _read_payments(project_root: Path) -> list:
    """결제 레저 목록 (tx_hash별 기록)."""
    p = _payments_path(project_root)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _append_payment(project_root: Path, record: Dict[str, Any]) -> None:
    """결제 기록 추가 (동일 tx_hash 중복 방지는 호출측에서 처리)."""
    if _is_vercel():
        logger.info("[VERCEL] Skipping file write for payment record.")
        return

    try:
        path = _payments_path(project_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        records = _read_payments(project_root)
        records.append(record)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
    except Exception as e:
        logger.error(f"Failed to write payment record: {e}")


def _find_payment_by_tx_hash(project_root: Path, tx_hash: str) -> Dict[str, Any] | None:
    """tx_hash로 이미 검증된 결제 기록 조회 (idempotency)."""
    key = str(tx_hash).strip().lower()
    for r in _read_payments(project_root):
        if str(r.get("tx_hash", "")).strip().lower() == key and str(r.get("verification_result")) == "pass":
            return r
    return None


def _read_download_tokens(project_root: Path) -> Dict[str, Dict[str, Any]]:
    """download_tokens.json: token -> {order_id, product_id, expires_at, use_count, max_uses}"""
    p = _download_tokens_path(project_root)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_download_tokens(project_root: Path, data: Dict[str, Dict[str, Any]]) -> None:
    if _is_vercel():
        return

    try:
        path = _download_tokens_path(project_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
    except Exception as e:
        logger.error(f"Failed to write download tokens: {e}")


def _append_download_log(project_root: Path, entry: Dict[str, Any]) -> None:
    """다운로드 이벤트 로그 추가."""
    if _is_vercel():
        return

    try:
        path = _downloads_path(project_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = []
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(existing, list):
                    existing = []
            except Exception:
                existing = []
        existing.append(entry)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
    except Exception as e:
        logger.error(f"Failed to append download log: {e}")


# -----------------------------
# EVM 설정 및 상품 가격(wei)
# -----------------------------

def get_evm_config(project_root: Path) -> Dict[str, Any]:
    """환경변수 기반 EVM 결제 설정."""
    _load_env(project_root)
    chain_id = int(os.getenv("CHAIN_ID", "1"))
    rpc_url = (os.getenv("RPC_URL") or "").strip()
    if not rpc_url and chain_id == 1:
        rpc_url = "https://eth.llamarpc.com"
    if not rpc_url and chain_id == 137:
        rpc_url = "https://polygon-rpc.com"
    if not rpc_url and chain_id == 8453:
        rpc_url = "https://mainnet.base.org"
    return {
        "merchant_wallet_address": (os.getenv("MERCHANT_WALLET_ADDRESS") or "").strip().lower(),
        "chain_id": chain_id,
        "rpc_url": rpc_url,
        "token_symbol": (os.getenv("TOKEN_SYMBOL") or "ETH").strip(),
        "price_wei_default": int(os.getenv("PRICE_WEI", "0"), 10),
        "download_token_ttl_seconds": int(os.getenv("DOWNLOAD_TOKEN_TTL_SECONDS", "900"), 10),
        "download_token_max_uses": int(os.getenv("DOWNLOAD_TOKEN_MAX_USES", "3"), 10),
    }


def get_product_price_wei(project_root: Path, product_id: str) -> int:
    """상품별 결제 금액(wei). 상품 메타(schema/manifest) 또는 기본값."""
    cfg = get_evm_config(project_root)
    # 기본값 설정 (환경변수 없으면 0)
    env_default = cfg.get("price_wei_default") or 0
    
    product_dir = project_root / "outputs" / product_id
    
    # 1. product_schema.json 확인 (랜딩페이지와 일치시키기 위해 우선순위 높임)
    schema_path = product_dir / "product_schema.json"
    if schema_path.exists():
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            
            # _injected_price 우선 확인 (생성 시점에 결정된 최종 가격)
            injected = schema.get("_injected_price")
            price_str = ""
            if injected and isinstance(injected, str) and injected.startswith("$"):
                price_str = injected
            else:
                price_str = schema.get("sections", {}).get("pricing", {}).get("price", "")

            if price_str:
                price_val = float(re.sub(r'[^\d.]', '', price_str))
                # $1 = 0.0004 ETH ($2500 기준) 수준으로 변환하여 차별화
                # 예: $29 -> 29 * 4 * 1e14 = 1.16e16 Wei (0.0116 ETH)
                return int(price_val * 4 * 1e14) 
        except Exception as e:
            logger.error(f"Failed to parse product_schema.json for {product_id}: {e}")
            pass

    # 2. manifest.json 확인
    manifest_path = product_dir / "manifest.json"
    if manifest_path.exists():
        try:
            m = json.loads(manifest_path.read_text(encoding="utf-8"))
            price_usd = m.get("price_usd")
            if price_usd:
                return int(float(price_usd) * 4 * 1e14)
        except Exception as e:
            logger.error(f"Failed to parse manifest.json for {product_id}: {e}")
            pass

    # 3. report.json (기존 호환성)
    report_path = product_dir / "report.json"
    if report_path.exists():
        try:
            meta = json.loads(report_path.read_text(encoding="utf-8"))
            if isinstance(meta, dict):
                w = meta.get("price_wei")
                if w is not None:
                    return int(w)
        except Exception:
            pass
            
    # Fallback: 만약 스키마 파싱에 실패했다면, 엉뚱한 값(0.01 ETH)보다는 에러를 내거나 명시적인 값을 써야 함.
    # 하지만 기존 로직 유지를 위해 env_default가 있으면 쓰고, 없으면 0.01 ETH(1e16) 사용.
    if env_default > 0:
        return env_default
        
    return int(1e16)  # 0.01 ETH fallback


# -----------------------------
# EVM 주문 생성 / 온체인 검증 / 다운로드 토큰(opaque)
# -----------------------------

def create_order_evm(
    project_root: Path,
    product_id: str,
    buyer_wallet: str | None = None,
) -> Dict[str, Any]:
    """EVM 결제용 주문 생성. 상태 PENDING_PAYMENT, meta에 expected_amount_wei 등 저장."""
    _load_env(project_root)
    store = get_order_store(project_root)
    cfg = get_evm_config(project_root)
    if not cfg.get("merchant_wallet_address"):
        return {"error": "merchant_wallet_not_configured", "order_id": ""}
    expected_wei = get_product_price_wei(project_root, product_id)
    order_id = new_order_id()
    now = _project_iso_now()
    meta = {
        "buyer_wallet": (buyer_wallet or "").strip().lower() or None,
        "chain_id": cfg["chain_id"],
        "expected_amount_wei": expected_wei,
        "evm_tx_hash": None,
        "evm_paid_at": None,
        "download_token": None,
    }
    order = Order(
        order_id=order_id,
        product_id=product_id,
        amount=0.0,
        currency=cfg.get("token_symbol", "ETH"),
        status="PENDING_PAYMENT",
        created_at=now,
        provider="evm",
        provider_payment_id="",
        provider_invoice_url="",
        meta=meta,
    )
    store.upsert(order)
    logger.info("EVM 주문 생성 order_id=%s product_id=%s expected_wei=%s", order_id, product_id, expected_wei)
    return {
        "order_id": order_id,
        "product_id": product_id,
        "status": "PENDING_PAYMENT",
        "expected_amount_wei": expected_wei,
        "chain_id": cfg["chain_id"],
        "merchant_wallet_address": cfg["merchant_wallet_address"],
        "rpc_url": cfg.get("rpc_url"),
        "token_symbol": cfg.get("token_symbol", "ETH"),
    }


def verify_evm_payment(
    project_root: Path,
    tx_hash: str,
    chain_id: int,
    product_id: str,
    buyer_wallet: str | None,
    order_id: str | None = None,
) -> Dict[str, Any]:
    """
    온체인 결제 검증 후 주문 PAID 처리 및 다운로드 토큰 발급.
    - 동일 tx_hash 재요청 시 기존 결과 반환(idempotency).
    - 검증 실패 시 verification_result=fail 기록, 주문은 변경하지 않음.
    """
    _load_env(project_root)
    store = get_order_store(project_root)
    cfg = get_evm_config(project_root)
    merchant = cfg.get("merchant_wallet_address")
    rpc_url = (cfg.get("rpc_url") or "").strip()
    tx_hash = tx_hash.strip()
    if not tx_hash:
        return {"ok": False, "error": "tx_hash_required"}
    if not merchant:
        return {"ok": False, "error": "merchant_wallet_not_configured"}
    if not rpc_url:
        return {"ok": False, "error": "rpc_url_not_configured"}

    # Idempotency: 이미 이 tx_hash로 결제 완료된 주문이 있는지 확인
    existing = _find_payment_by_tx_hash(project_root, tx_hash)
    if existing:
        oid = existing.get("order_id")
        order = store.get(oid) if oid else None
        if order and str(order.get("status")) == "paid":
            token = (order.get("meta") or {}).get("download_token")
            if token:
                logger.info("EVM 검증 idempotent: tx_hash=%s order_id=%s", tx_hash[:16], oid)
                return {
                    "ok": True,
                    "order_id": oid,
                    "already_verified": True,
                    "download_token": token,
                    "download_url": f"/download_token/{token}",
                }
        return {"ok": False, "error": "tx_hash_already_used", "order_id": oid}

    # 주문 결정: order_id가 있으면 해당 주문, 없으면 product_id로 PENDING_PAYMENT 주문 찾기
    if order_id:
        order = store.get(order_id)
    else:
        orders = store.list_orders()
        order = None
        for o in orders:
            if str(o.get("product_id")) == product_id and str(o.get("status")) == "PENDING_PAYMENT":
                order = o
                break
        if not order:
            order = None
    if not order:
        return {"ok": False, "error": "order_not_found"}

    expected_wei = (order.get("meta") or {}).get("expected_amount_wei")
    if expected_wei is None:
        expected_wei = get_product_price_wei(project_root, product_id)
    else:
        expected_wei = int(expected_wei)
    if int(chain_id) != int((order.get("meta") or {}).get("chain_id", 0)):
        return {"ok": False, "error": "chain_id_mismatch"}

    # 온체인 검증
    from_addr = (buyer_wallet or "").strip().lower() or None
    result = evm_verify_on_chain(
        rpc_url=rpc_url,
        tx_hash=tx_hash,
        merchant_address=merchant,
        expected_amount_wei=expected_wei,
        chain_id=int(chain_id),
        from_address=from_addr,
    )
    now_iso = _project_iso_now()

    if not result.get("ok"):
        _append_payment(project_root, {
            "tx_hash": tx_hash,
            "order_id": order.get("order_id"),
            "chain_id": chain_id,
            "from_wallet": result.get("from_wallet"),
            "to_wallet": result.get("to_wallet"),
            "value_wei": result.get("value_wei"),
            "confirmed_block": result.get("block_number"),
            "verified_at": now_iso,
            "verification_result": "fail",
            "reason": result.get("error"),
        })
        logger.warning("EVM 검증 실패 tx_hash=%s reason=%s", tx_hash[:16], result.get("error"))
        return {"ok": False, "error": result.get("error", "verification_failed")}

    # 결제 기록 저장
    _append_payment(project_root, {
        "tx_hash": tx_hash,
        "order_id": order.get("order_id"),
        "chain_id": chain_id,
        "from_wallet": result.get("from_wallet"),
        "to_wallet": result.get("to_wallet"),
        "value_wei": result.get("value_wei"),
        "confirmed_block": result.get("block_number"),
        "verified_at": now_iso,
        "verification_result": "pass",
    })
    store.update_status(order["order_id"], "paid")
    token = issue_opaque_download_token(
        project_root,
        order_id=order["order_id"],
        product_id=order["product_id"],
        ttl_seconds=cfg.get("download_token_ttl_seconds", 900),
        max_uses=cfg.get("download_token_max_uses", 3),
    )
    store.update_meta(order["order_id"], {
        "evm_tx_hash": tx_hash,
        "evm_paid_at": now_iso,
        "download_token": token,
    })
    logger.info("EVM 결제 검증 완료 order_id=%s tx_hash=%s", order["order_id"], tx_hash[:16])
    return {
        "ok": True,
        "order_id": order["order_id"],
        "download_token": token,
        "download_url": f"/download_token/{token}",
    }


def issue_opaque_download_token(
    project_root: Path,
    *,
    order_id: str,
    product_id: str,
    ttl_seconds: int = 900,
    max_uses: int = 3,
) -> str:
    """추측 불가능한 다운로드 토큰 발급 후 레저에 저장 (TTL + max_uses)."""
    import secrets as sec
    token = sec.token_urlsafe(32)
    now = int(time.time())
    expires_at = now + ttl_seconds
    data = _read_download_tokens(project_root)
    data[token] = {
        "order_id": order_id,
        "product_id": product_id,
        "expires_at": expires_at,
        "use_count": 0,
        "max_uses": max_uses,
    }
    _write_download_tokens(project_root, data)
    return token


def validate_download_token_and_consume(
    project_root: Path,
    token: str,
    log_download: bool = True,
    ip: str | None = None,
    user_agent: str | None = None,
) -> Dict[str, Any]:
    """
    opaque 토큰 검증 후 사용 횟수 증가.
    반환: {ok, order_id, product_id, package_path} 또는 {ok: False, error}.
    """
    data = _read_download_tokens(project_root)
    rec = data.get(token)
    if not rec:
        return {"ok": False, "error": "token_not_found"}
    now = int(time.time())
    if now > int(rec.get("expires_at", 0)):
        return {"ok": False, "error": "token_expired"}
    use_count = int(rec.get("use_count", 0))
    max_uses = int(rec.get("max_uses", 1))
    if use_count >= max_uses:
        return {"ok": False, "error": "token_max_uses_exceeded"}
    rec["use_count"] = use_count + 1
    data[token] = rec
    _write_download_tokens(project_root, data)
    if log_download:
        _append_download_log(project_root, {
            "token": token[:16] + "...",
            "order_id": rec.get("order_id"),
            "product_id": rec.get("product_id"),
            "downloaded_at": _project_iso_now(),
            "ip": ip,
            "user_agent": user_agent,
            "count": rec["use_count"],
        })
    pkg = get_package_path(project_root, rec["product_id"])
    if not pkg.exists():
        return {"ok": False, "error": "package_not_found", "product_id": rec["product_id"]}
    return {
        "ok": True,
        "order_id": rec["order_id"],
        "product_id": rec["product_id"],
        "package_path": str(pkg),
        "filename": f"{rec['product_id']}-package.zip",
    }


# -----------------------------
# Business API
# -----------------------------


def _project_iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def start_order(
    project_root: Path, product_id: str, amount: float, currency: str
) -> Dict[str, Any]:
#     """주문 생성 + 결제 생성(가능하면 NOWPayments)."""
    _load_env(project_root)

    store = get_order_store(project_root)
    order_id = new_order_id()

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
            status = "pending"
        except NowPaymentsError:
            # 운영 안정성: 실패하면 simulated로 폴백(결제 없이 다운로드를 열지 않도록 status는 pending 유지)
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
        meta={"note": "created", "used_download_jti": []},
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


def check_order(project_root: Path, order_id: str) -> Dict[str, Any]:
    """주문 상태 조회 + (NOWPayments면) provider 상태 반영."""
    _load_env(project_root)

    store = get_order_store(project_root)
    order = store.get(order_id)
    if not order:
        return {"error": "order_not_found", "order_id": order_id, "status": "not_found"}

    status = str(order.get("status", "pending"))

    # NOWPayments polling으로 상태 갱신
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
                pass

    can_download = status in ("paid", "delivered")
    product_id = str(order.get("product_id") or "")
    download_url = ""
    token = ""
    if can_download and product_id:
        # 토큰 발급(짧은 TTL + 기본 1회용)
        token = issue_download_token(
            project_root,
            order_id=order_id,
            product_id=product_id,
            ttl_seconds=900,
            one_time=True,
        )
        download_url = f"/api/pay/download?order_id={order_id}&token={token}"

    return {
        "order_id": order_id,
        "product_id": product_id,
        "status": status,
        "can_download": bool(can_download),
        "download_url": download_url,
        "token": token,
    }


def download_for_order(
    project_root: Path, *, order_id: str, token: str
) -> Dict[str, Any]:
#     """다운로드 요청을 검사하고 파일 경로/메타를 반환한다."""
    store = get_order_store(project_root)
    order = store.get(order_id)
    if not order:
        return {"error": "order_not_found", "status": 404}

    # token 검증
    v = verify_download_token(project_root, token)
    if not v.get("ok"):
        return {"error": "invalid_token", "detail": v, "status": 401}

    if str(v.get("order_id")) != str(order_id):
        return {"error": "token_order_mismatch", "status": 401}

    product_id = str(order.get("product_id") or "")
    if str(v.get("product_id")) != str(product_id):
        return {"error": "token_product_mismatch", "status": 401}

    status = str(order.get("status", "pending"))
    if status not in ("paid", "delivered"):
        return {"error": "not_paid", "status": 403, "order_status": status}

    # 1회용 토큰 소비
    cons = consume_token_if_needed(
        project_root,
        order_id=order_id,
        jti=str(v.get("jti") or ""),
        one_time=bool(v.get("one_time")),
    )
    if not cons.get("ok"):
        return {"error": cons.get("error"), "status": 403}

    pkg = get_package_path(project_root, product_id)
    if not pkg.exists():
        return {"error": "package_not_found", "status": 404, "product_id": product_id}

    return {
        "ok": True,
        "status": 200,
        "product_id": product_id,
        "package_path": str(pkg),
        "filename": f"{product_id}-package.zip",
        "token_consumed": bool(cons.get("consumed")),
    }


# ================================
# Compatibility shim for dashboard
# ================================
# dashboard_server.py에서 mark_paid_testonly를 import하는데,
# 일부 버전에서 함수가 없어서 ImportError가 발생할 수 있다.
# 아래는 호환용(테스트/로컬운영용) 엔드포인트에서 사용하도록 만든 래퍼 함수다.

import json  # JSON 저장용
from datetime import datetime  # 시간 기록용


def _safe_write_json(path: Path, data: dict) -> None:
    """딕셔너리를 JSON 파일로 안전하게 저장한다."""
    path.parent.mkdir(parents=True, exist_ok=True)  # 폴더 없으면 생성
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )  # JSON 저장


def mark_paid_testonly(
    order_id: str,
    amount: float = 0.0,
    currency: str = "USDT",
    project_root: Path | None = None,
) -> dict:
    """
    테스트 전용: 주문을 paid로 마킹.
    - project_root가 주어지면 order_store의 해당 주문 상태를 'paid'로 갱신.
    - 운영에서는 ALLOW_TEST_MARK_PAID=1 일 때만 노출 권장.
    """
    if project_root is not None:
        store = get_order_store(project_root)
        order = store.get(order_id)
        if order:
            store.update_status(order_id, "paid")
            store.update_meta(order_id, {"evm_paid_at": _project_iso_now(), "mode": "testonly"})
    
    if _is_vercel():
        return {"status": "paid", "mode": "testonly", "note": "Vercel: File write skipped"}

    # 로컬 테스트 ledger에도 기록 (호환용)
    ledger_path = project_root / "data" / "payments" / "testonly_ledger.json" if project_root else Path("data") / "payments" / "testonly_ledger.json"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    if ledger_path.exists():
        try:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        except Exception:
            ledger = {}
    else:
        ledger = {}
    ledger[str(order_id)] = {
        "status": "paid",
        "amount": float(amount),
        "currency": str(currency),
        "mode": "testonly",
        "paid_at": datetime.utcnow().isoformat() + "Z",
    }
    _safe_write_json(ledger_path, ledger)
    return {
        "ok": True,
        "order_id": str(order_id),
        "status": "paid",
        "amount": float(amount),
        "currency": str(currency),
        "mode": "testonly",
        "ledger_path": str(ledger_path),
    }
