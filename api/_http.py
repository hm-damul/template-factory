# api/_http.py
# Vercel Python 런타임(WSGI/Handler 혼재)에서 공통으로 응답을 만드는 유틸
# - 어떤 런타임은 dict({statusCode, headers, body}) 반환을 기대
# - 어떤 런타임은 BaseHTTPRequestHandler 스타일을 사용
# => 둘 다 지원하도록 방어적으로 작성

import json
from typing import Any, Dict, Optional


def _is_handler(obj: Any) -> bool:
    # BaseHTTPRequestHandler 유사 객체인지 확인
    return (
        hasattr(obj, "send_response")
        and hasattr(obj, "send_header")
        and hasattr(obj, "end_headers")
        and hasattr(obj, "wfile")
    )


def send_json(
    req_or_handler: Any,
    payload: Dict[str, Any],
    status: int = 200,
    headers: Optional[Dict[str, str]] = None,
):
    # JSON 응답 생성(런타임 호환)
    hdrs = {
        "Content-Type": "application/json; charset=utf-8",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type, X-Nowpayments-Sig",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    }
    if headers:
        hdrs.update(headers)

    body = json.dumps(payload, ensure_ascii=False)

    if _is_handler(req_or_handler):
        h = req_or_handler
        h.send_response(status)
        for k, v in hdrs.items():
            h.send_header(k, v)
        h.end_headers()
        h.wfile.write(body.encode("utf-8"))
        return None

    # dict 반환 타입
    return {"statusCode": status, "headers": hdrs, "body": body}


def send_text(
    req_or_handler: Any,
    text: str,
    status: int = 200,
    headers: Optional[Dict[str, str]] = None,
):
    hdrs = {
        "Content-Type": "text/plain; charset=utf-8",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type, X-Nowpayments-Sig",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    }
    if headers:
        hdrs.update(headers)

    if _is_handler(req_or_handler):
        h = req_or_handler
        h.send_response(status)
        for k, v in hdrs.items():
            h.send_header(k, v)
        h.end_headers()
        h.wfile.write(text.encode("utf-8"))
        return None

    return {"statusCode": status, "headers": hdrs, "body": text}
