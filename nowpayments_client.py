# -*- coding: utf-8 -*-
"""
nowpayments_client.py

목적:
- NOWPayments 결제 생성/조회 기능을 "얇게" 래핑한다.
- API KEY가 없으면 예외를 던지지 않고, 호출자가 simulated 모드로 fallback 할 수 있게 한다.

참고:
- NOWPayments는 API 키 기반(x-api-key 헤더).
- 여기서는 최소 기능만 구현한다:
  - create_payment: 결제 생성 -> payment_id / invoice_url 반환
  - get_payment_status: payment_id로 상태 조회

주의:
- 실제 운영에서는 IPN(webhook) 기반으로 status를 업데이트하는 것이 안정적이다.
  (이 프로젝트는 우선 polling 기반 check로 구현)
"""

from __future__ import annotations

import os  # env
from typing import Any, Dict, Optional  # 타입

import requests  # HTTP

NOWPAYMENTS_BASE_URL = os.getenv(
    "NOWPAYMENTS_BASE_URL", "https://api.nowpayments.io"
).rstrip("/")


class NowPaymentsError(RuntimeError):
    pass


import json

def _load_secrets():
    try:
        # Try to locate secrets.json relative to this file
        # If this file is in src/, secrets is in ../data/secrets.json
        # If this file is in api/, secrets might be in data/secrets.json (copied)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Check standard locations
        paths = [
            os.path.join(base_dir, "data", "secrets.json"),
            os.path.join(os.path.dirname(base_dir), "data", "secrets.json"),
            os.path.join(base_dir, "secrets.json"), # If copied to same dir
        ]
        
        for p in paths:
            if os.path.exists(p):
                with open(p, 'r', encoding='utf-8') as f:
                    return json.load(f)
    except Exception:
        pass
    return {}

def _get_api_key() -> str:
    # 1. Env Var
    key = os.getenv("NOWPAYMENTS_API_KEY", "").strip()
    if key:
        return key
        
    # 2. secrets.json
    secrets = _load_secrets()
    if not isinstance(secrets, dict):
        return ""
    return secrets.get("NOWPAYMENTS_API_KEY", "").strip()

def has_api_key() -> bool:
    """NOWPAYMENTS_API_KEY 존재 여부."""
    return bool(_get_api_key())


def _headers() -> Dict[str, str]:
    key = _get_api_key()
    if not key:
        raise NowPaymentsError("Missing NOWPAYMENTS_API_KEY")
    return {
        "x-api-key": key,
        "Content-Type": "application/json",
    }


def create_payment(
    order_id: str,
    product_id: str,
    amount: float,
    currency: str,
    success_url: Optional[str] = None,
    cancel_url: Optional[str] = None,
) -> Dict[str, Any]:
#     """결제 생성."""
    payload: Dict[str, Any] = {
        "price_amount": float(amount),
        "price_currency": (currency or "usd").lower(),
        "order_id": order_id,
        "order_description": f"Digital product: {product_id}",
    }
    if success_url:
        payload["success_url"] = success_url
    if cancel_url:
        payload["cancel_url"] = cancel_url

    r = requests.post(
        f"{NOWPAYMENTS_BASE_URL}/v1/payment",
        headers=_headers(),
        json=payload,
        timeout=20,
    )
    if r.status_code >= 400:
        raise NowPaymentsError(
            f"NOWPayments create_payment failed: {r.status_code} {r.text}"
        )
    data = r.json()
    return {
        "payment_id": str(data.get("payment_id", "")),
        "invoice_url": str(data.get("invoice_url", ""))
        or str(data.get("payment_url", "")),
        "pay_address": str(data.get("pay_address", "")),
        "pay_amount": data.get("pay_amount"),
        "pay_currency": data.get("pay_currency"),
        "raw": data,
    }


def get_payment_status(payment_id: str) -> Dict[str, Any]:
    """payment_id로 상태 조회."""
    if not payment_id:
        raise NowPaymentsError("payment_id is required")
    r = requests.get(
        f"{NOWPAYMENTS_BASE_URL}/v1/payment/{payment_id}",
        headers=_headers(),
        timeout=20,
    )
    if r.status_code >= 400:
        raise NowPaymentsError(
            f"NOWPayments get_payment_status failed: {r.status_code} {r.text}"
        )
    data = r.json()
    return {
        "payment_id": payment_id,
        "payment_status": str(data.get("payment_status", "")),
        "raw": data,
    }


def map_nowpayments_status_to_order(status: str) -> str:
    """NOWPayments 상태를 내부 order status로 매핑."""
    s = (status or "").lower()
    # 공식 상태가 다양할 수 있어 보수적으로 매핑
    if s in {"finished", "confirmed", "sending", "partially_paid", "paid"}:
        # partially_paid는 운영에서는 추가 확인이 필요하지만, 여기서는 paid로 취급(단순화)
        return "paid"
    if s in {"waiting", "confirming"}:
        return "pending"
    if s in {"expired"}:
        return "expired"
    if s in {"failed", "refunded"}:
        return "failed"
    # 알 수 없는 상태는 pending
    return "pending"
