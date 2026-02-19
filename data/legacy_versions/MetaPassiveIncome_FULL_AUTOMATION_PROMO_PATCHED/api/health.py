# -*- coding: utf-8 -*-
"""
api/health.py

Vercel Serverless:
- GET /api/health

배포된 환경에서 헬스체크 용도.
"""

from __future__ import annotations

from api._vercel_common import _get_method, _resp


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
    return _resp(200, {"ok": True, "service": "api", "env": "vercel"}, "GET, OPTIONS")
