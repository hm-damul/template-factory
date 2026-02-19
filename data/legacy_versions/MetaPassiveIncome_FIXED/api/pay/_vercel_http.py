# -*- coding: utf-8 -*-
"""
Vercel Python Serverless helper.

Vercel has had multiple Python runtimes over time:
- Older style: `handler(request: BaseHTTPRequestHandler) -> None` and you must write to `request.wfile`.
- Some environments / local emulators: returning a dict with `statusCode/headers/body`.

This helper supports BOTH.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional


def _is_base_http_handler(req: Any) -> bool:
    """Heuristic: BaseHTTPRequestHandler-like object has send_response + wfile."""
    return (
        hasattr(req, "send_response")
        and hasattr(req, "send_header")
        and hasattr(req, "end_headers")
        and hasattr(req, "wfile")
    )


def read_json_body(req: Any) -> Dict[str, Any]:
    """
    Read JSON body from either:
    - BaseHTTPRequestHandler-like object: `rfile` with Content-Length
    - Request-like object: `.body` bytes/str
    """
    # BaseHTTPRequestHandler path
    if hasattr(req, "rfile"):
        try:
            length = int(getattr(req, "headers", {}).get("content-length") or 0)
        except Exception:
            length = 0
        if length > 0:
            raw = req.rfile.read(length)
            try:
                return json.loads(raw.decode("utf-8"))
            except Exception:
                return {}
        return {}

    # Dict-returning style path
    try:
        body = getattr(req, "body", None)
        if body is None:
            return {}
        raw = body.decode("utf-8") if hasattr(body, "decode") else str(body)
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


def read_query(req: Any) -> Dict[str, str]:
    """Read querystring from either BaseHTTPRequestHandler path or request.query mapping."""
    # BaseHTTPRequestHandler: parse req.path
    if hasattr(req, "path"):
        try:
            from urllib.parse import parse_qs, urlparse

            q = parse_qs(urlparse(req.path).query)
            return {
                k: (v[0] if isinstance(v, list) and v else "") for k, v in q.items()
            }
        except Exception:
            return {}

    try:
        q = getattr(req, "query", None) or {}
        return {str(k): str(v) for k, v in q.items()}
    except Exception:
        return {}


def send_json(
    req: Any,
    status: int,
    payload: Dict[str, Any],
    extra_headers: Optional[Dict[str, str]] = None,
) -> Any:
    """
    Send JSON response in whichever runtime style is available.
    """
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Cache-Control": "no-store",
    }
    if extra_headers:
        headers.update(extra_headers)

    body = json.dumps(payload, ensure_ascii=False)

    # BaseHTTPRequestHandler-style
    if _is_base_http_handler(req):
        req.send_response(status)
        for k, v in headers.items():
            req.send_header(k, v)
        req.end_headers()
        req.wfile.write(body.encode("utf-8"))
        return None

    # Dict-returning style (works in some local tooling)
    return {"statusCode": status, "headers": headers, "body": body}


def handle_options(req: Any) -> Any:
    """CORS preflight."""
    return send_json(req, 200, {"ok": True})
