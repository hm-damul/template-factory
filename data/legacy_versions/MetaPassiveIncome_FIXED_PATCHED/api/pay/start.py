# -*- coding: utf-8 -*-
"""
api/pay/start.py  (Vercel Serverless Function - Python)
엔드포인트:
- OPTIONS /api/pay/start
- POST    /api/pay/start

동작(테스트 모드):
- 주문 생성 즉시 paid 반환
- 다운로드 링크: /downloads/<product_id>/package.zip

중요:
- 브라우저 fetch(JSON POST)는 CORS preflight(OPTIONS)를 발생시킬 수 있으므로,
  handler에서 OPTIONS를 반드시 처리하여 405를 제거한다.
"""

from __future__ import annotations

import json  # JSON 파싱/응답
import uuid  # order_id 생성


def _cors_headers() -> dict:
    """Vercel 응답용 CORS 헤더."""
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
    }


def handler(request):
    method = str(getattr(request, "method", "") or "").upper()

    if method == "OPTIONS":
        return {"statusCode": 204, "headers": _cors_headers(), "body": ""}

    if method != "POST":
        return {
            "statusCode": 405,
            "headers": _cors_headers(),
            "body": json.dumps(
                {"error": "Method Not Allowed. Use POST."}, ensure_ascii=False
            ),
        }

    try:
        raw = getattr(request, "body", b"") or b""
        if hasattr(raw, "decode"):
            raw = raw.decode("utf-8", errors="replace")
        data = json.loads(raw) if raw else {}
    except Exception:
        data = {}

    product_id = str(data.get("product_id") or "").strip()
    if not product_id:
        return {
            "statusCode": 400,
            "headers": _cors_headers(),
            "body": json.dumps({"error": "product_id is required"}, ensure_ascii=False),
        }

    order_id = str(uuid.uuid4())
    download_url = f"/downloads/{product_id}/package.zip"

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
