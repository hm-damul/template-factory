# -*- coding: utf-8 -*-
"""
api/pay/start.py

Vercel Serverless:
- OPTIONS /api/pay/start
- POST    /api/pay/start

로직은 payment_api.py를 사용한다.
"""

from __future__ import annotations

from pathlib import Path

from api._vercel_common import _get_method, _read_json, _resp
from payment_api import start_order


def handler(request):
    method = _get_method(request)

    if method == "OPTIONS":
        return {
            "statusCode": 204,
            "headers": {**_resp(200, {}, "POST, OPTIONS")["headers"]},
            "body": "",
        }

    if method != "POST":
        return _resp(405, {"error": "Method Not Allowed. Use POST."}, "POST, OPTIONS")

    data = _read_json(request)
    product_id = str(data.get("product_id", "")).strip()
    amount = float(data.get("amount", 29.0))
    currency = str(data.get("currency", "usd")).lower().strip() or "usd"

    if not product_id:
        return _resp(400, {"error": "product_id_required"}, "POST, OPTIONS")

    project_root = Path(__file__).resolve().parents[2]
    resp = start_order(
        project_root=project_root,
        product_id=product_id,
        amount=amount,
        currency=currency,
    )
    return _resp(200, resp, "POST, OPTIONS")
