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
import os
import sys
from pathlib import Path
from typing import Any, Dict


def _ensure_env():
    """Vercel 환경변수 및 로컬 secrets.json 로드."""
    # Vercel 환경에서는 이미 환경변수가 주입되어 있음.
    # 로컬 테스트 시에만 secrets.json 등을 로드.
    if os.getenv("VERCEL") == "1" or "NOW_REGION" in os.environ:
        return

    root = Path(__file__).resolve().parents[1]
    # 1) .env 로드 시도
    try:
        from dotenv import load_dotenv
        for cand in [root / ".env", root / ".env.local"]:
            if cand.exists():
                load_dotenv(dotenv_path=str(cand))
    except ImportError:
        pass

    # 2) data/secrets.json 로드 시도
    secrets_path = root / "data" / "secrets.json"
    if secrets_path.exists():
        try:
            data = json.loads(secrets_path.read_text(encoding="utf-8"))
            for k, v in data.items():
                if not os.getenv(k) and isinstance(v, str):
                    os.environ[k] = v
        except Exception:
            pass

# 초기화 시 환경 로드
_ensure_env()


def _cors_headers(allow_methods: str) -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Allow-Methods": allow_methods,
    }


def _get_method(req: Any) -> str:
    # 1. Try .method (Flask/Werkzeug)
    m = getattr(req, "method", "")
    if m:
        return str(m).upper()
    
    # 2. Try .command (BaseHTTPRequestHandler / Vercel legacy)
    c = getattr(req, "command", "")
    if c:
        return str(c).upper()
        
    # 3. Try .environ (WSGI)
    env = getattr(req, "environ", {})
    if isinstance(env, dict):
        e = env.get("REQUEST_METHOD", "")
        if e:
            return str(e).upper()
            
    return "GET"  # Fallback to GET if unknown, to avoid 405 blocking everything


def _read_json(req: Any) -> Dict[str, Any]:
    # 1. Try .body (Flask/Vercel legacy raw)
    raw = getattr(req, "body", b"") or b""
    
    # 2. Try .rfile (BaseHTTPRequestHandler)
    if not raw and hasattr(req, "rfile") and hasattr(req, "headers"):
        try:
            cl = int(req.headers.get("Content-Length", 0))
            if cl > 0:
                raw = req.rfile.read(cl)
        except Exception:
            pass

    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}


def _get_query_param(req: Any, key: str) -> str:
    # 1) Try req.query (if Vercel provides it)
    q = getattr(req, "query", None)
    if isinstance(q, dict) and key in q:
        val = q.get(key)
        return str(val) if val is not None else ""
    
    # 2) Parse from URL or Path
    url = str(getattr(req, "url", "") or "")
    if not url:
        url = str(getattr(req, "path", "") or "")

    if "?" in url:
        from urllib.parse import parse_qs, urlparse
        # Handle full URL or path only
        if "://" not in url:
            url = "http://dummy" + url
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if key in qs:
            return str(qs[key][0])
    return ""


def _resp(status: int, body: Any, allow: str = "GET, POST, OPTIONS") -> Dict[str, Any]:
    if isinstance(body, dict):
        body_str = json.dumps(body, ensure_ascii=False)
    else:
        body_str = str(body)
    
    headers = _cors_headers(allow)
    
    return {
        "statusCode": status,
        "headers": headers,
        "body": body_str,
    }
