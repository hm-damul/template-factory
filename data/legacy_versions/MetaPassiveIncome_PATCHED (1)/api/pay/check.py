# -*- coding: utf-8 -*-
"""
api/pay/check.py

Vercel Serverless:
- OPTIONS /api/pay/check
- GET     /api/pay/check?order_id=...

로직은 payment_api.py를 사용한다.
"""

from __future__ import annotations

from pathlib import Path

from api._vercel_common import _get_method, _resp
from payment_api import check_order


def _get_query_param(req, key: str) -> str:
    # Vercel 런타임에 따라 query dict가 있을 수 있음
    q = getattr(req, "query", None)
    if isinstance(q, dict) and key in q:
        return str(q.get(key) or "")
    # 일부 런타임은 req.url 에 ?a=b 형태로 들어올 수 있음
    url = str(getattr(req, "url", "") or "")
    if "?" in url:
        qs = url.split("?", 1)[1]
        for part in qs.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                if k == key:
                    return v
    return ""


def handler(request):
    method = _get_method(request)

    if method == "OPTIONS":
        return {
            "statusCode": 204,
            "headers": {**_resp(200, {}, "GET, OPTIONS")["headers"]},
            "body": "",
        }

    if method != "GET":
        return _resp(405, {"error": "Method Not Allowed. Use GET."}, "GET, OPTIONS")

    order_id = _get_query_param(request, "order_id").strip()
    if not order_id:
        return _resp(400, {"error": "order_id_required"}, "GET, OPTIONS")

    project_root = Path(__file__).resolve().parents[2]
    resp = check_order(project_root=project_root, order_id=order_id)
    return _resp(200, resp, "GET, OPTIONS")
