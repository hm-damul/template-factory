# -*- coding: utf-8 -*-
"""
Vercel Python Serverless Function helper.

- 일부 런타임은 request.body (bytes) + request.method 를 제공한다.
- 일부는 BaseHTTPRequestHandler 스타일로 들어올 수 있다.

이 helper는 두 케이스를 모두 처리하고,
반환은 dict {statusCode, headers, body} 스타일로 통일한다.
"""

from __future__ import annotations

import json
from typing import Any, Dict


def _cors_headers(allow_methods: str) -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Allow-Methods": allow_methods,
    }


def _get_method(req: Any) -> str:
    return str(getattr(req, "method", "") or "").upper()


def _read_json(req: Any) -> Dict[str, Any]:
    raw = getattr(req, "body", b"") or b""
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}


def _resp(status: int, body_obj, allow_methods: str) -> Dict[str, Any]:
    return {
        "statusCode": int(status),
        "headers": _cors_headers(allow_methods),
        "body": json.dumps(body_obj, ensure_ascii=False),
    }
