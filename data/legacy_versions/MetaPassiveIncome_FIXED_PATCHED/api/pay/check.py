# -*- coding: utf-8 -*-
"""
api/pay/check.py  (Vercel Serverless Function - Python)
엔드포인트:
- OPTIONS /api/pay/check
- GET     /api/pay/check?order_id=...&product_id=...

동작(테스트 모드):
- 항상 paid 반환
- download_url: /downloads/<product_id>/package.zip

중요:
- preflight(OPTIONS) 처리로 405 제거
"""

from __future__ import annotations

import json  # JSON 응답


def _cors_headers() -> dict:
    """Vercel 응답용 CORS 헤더."""
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
    }


def handler(request):
    method = str(getattr(request, "method", "") or "").upper()

    if method == "OPTIONS":
        return {"statusCode": 204, "headers": _cors_headers(), "body": ""}

    if method != "GET":
        return {
            "statusCode": 405,
            "headers": _cors_headers(),
            "body": json.dumps(
                {"error": "Method Not Allowed. Use GET."}, ensure_ascii=False
            ),
        }

    try:
        qs = getattr(request, "query", None) or {}
    except Exception:
        qs = {}

    order_id = str(qs.get("order_id") or "").strip()
    product_id = str(qs.get("product_id") or "").strip()

    if not order_id:
        return {
            "statusCode": 400,
            "headers": _cors_headers(),
            "body": json.dumps({"error": "order_id is required"}, ensure_ascii=False),
        }

    download_url = f"/downloads/{product_id}/package.zip" if product_id else ""

    return {
        "statusCode": 200,
        "headers": _cors_headers(),
        "body": json.dumps(
            {
                "order_id": order_id,
                "status": "paid",
                "product_id": product_id,
                "download_url": download_url,
            },
            ensure_ascii=False,
        ),
    }
