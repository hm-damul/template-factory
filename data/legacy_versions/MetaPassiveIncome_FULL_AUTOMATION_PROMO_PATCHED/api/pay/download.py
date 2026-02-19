# -*- coding: utf-8 -*-
"""
api/pay/download.py

Vercel Serverless:
- OPTIONS /api/pay/download
- GET     /api/pay/download?order_id=...

주의:
- Serverless에서 바이너리 응답은 런타임/설정에 따라 제한될 수 있다.
- 여기서는 base64 인코딩 없이 "바이너리 직접"을 시도한다.
  (Vercel Python 런타임이 dict 반환 방식을 사용할 때는 보통 base64가 필요할 수 있음)

따라서:
- 로컬에서는 backend/payment_server.py가 확실히 다운로드를 제공한다.
- 배포에서는 우선 JSON으로 다운로드 URL을 제공하고,
  실제 다운로드는 /downloads/... 정적 파일로 우회할 수 있다.
  (하지만 정적 파일은 게이팅이 어렵다)

현실적인 운영:
- 배포 운영에서는 Upstash + server-side streaming 가능한 런타임/플랫폼을 권장.
"""

from __future__ import annotations

import base64
from pathlib import Path

from api._vercel_common import _get_method, _resp
from payment_api import download_for_order


def _get_query_param(req, key: str) -> str:
    q = getattr(req, "query", None)
    if isinstance(q, dict) and key in q:
        return str(q.get(key) or "")
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
        # 파일 응답이라도 OPTIONS는 204로 처리
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
    info = download_for_order(project_root=project_root, order_id=order_id)
    if not info.get("ok"):
        return _resp(int(info.get("status", 400)), info, "GET, OPTIONS")

    # Vercel dict-style binary 응답 호환을 위해 base64 인코딩
    p = Path(str(info["package_path"]))
    data = p.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")

    headers = {
        "Content-Type": "application/zip",
        "Content-Disposition": f"attachment; filename=\"{info.get('filename') or 'package.zip'}\"",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Content-Transfer-Encoding": "base64",
    }
    return {"statusCode": 200, "headers": headers, "body": b64, "isBase64Encoded": True}
