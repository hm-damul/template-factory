# -*- coding: utf-8 -*-
"""
backend/payment_server.py
- 목적: 로컬 테스트 결제 API 서버
  - /api/pay/start    : 주문 생성 (테스트 모드: 즉시 paid 처리)
  - /api/pay/check    : 결제 상태 확인
  - /api/pay/download : 결제 완료된 주문에 대해 파일 다운로드 제공
  - /health           : 헬스체크

- 포트: 5000
- 주의: 이 서버는 "로컬 테스트" 목적이다.
        운영 단계에서는 download_file_path를 클라이언트가 보내는 구조를 사용하면 안 된다.
        (서버에 사전 등록된 상품ID → 파일경로 매핑 / 토큰 기반 인증으로 바꾸는 것이 정석)
"""

from __future__ import annotations

import os  # 파일 존재 확인
import uuid  # 주문 ID 생성
from typing import Any, Dict  # 타입 힌트

from flask import (
    Flask,
    jsonify,
    make_response,
    request,  # Flask 기본 구성요소
    send_file,
)

# flask-cors가 있으면 사용하고, 없으면 수동으로 CORS 헤더를 붙인다.
try:
    from flask_cors import CORS  # type: ignore

    _HAS_CORS = True
except Exception:
    CORS = None
    _HAS_CORS = False

app = Flask(__name__)

if _HAS_CORS and CORS:
    # 개발 편의를 위해 전체 허용 (로컬 테스트)
    CORS(app, resources={r"/*": {"origins": "*"}})

# 메모리 주문 저장소(테스트용)
# order_id -> {status, product_id, download_file_path}
ORDERS: Dict[str, Dict[str, Any]] = {}


def _add_cors_headers(resp):
    """flask-cors가 없을 때를 대비한 수동 CORS 헤더 추가."""
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    return resp


@app.before_request
def handle_preflight():
    """브라우저 preflight(OPTIONS) 요청 처리."""
    if request.method == "OPTIONS":
        resp = make_response("", 204)
        return _add_cors_headers(resp)
    return None


@app.after_request
def after(resp):
    """모든 응답에 CORS 헤더 보강(중복되어도 무방)."""
    return _add_cors_headers(resp)


@app.get("/health")
def health():
    """헬스체크 엔드포인트."""
    return jsonify({"ok": True, "service": "payment_server", "orders": len(ORDERS)})


@app.post("/api/pay/start")
def pay_start():
    """
    주문 생성
    입력(JSON):
      - product_id: str
      - download_file_path: str (로컬 테스트 단계에서만 허용)
    출력(JSON):
      - order_id: str
      - status: "paid" (테스트 모드이므로 즉시 paid)
    """
    data = request.get_json(silent=True) or {}

    product_id = str(data.get("product_id") or "").strip()
    download_file_path = str(data.get("download_file_path") or "").strip()

    if not product_id:
        return jsonify({"error": "product_id is required"}), 400

    if not download_file_path:
        return jsonify({"error": "download_file_path is required (test mode)"}), 400

    if not os.path.exists(download_file_path):
        return (
            jsonify({"error": f"download_file_path not found: {download_file_path}"}),
            404,
        )

    order_id = str(uuid.uuid4())

    # 테스트 모드: 즉시 결제 완료 처리
    ORDERS[order_id] = {
        "status": "paid",
        "product_id": product_id,
        "download_file_path": download_file_path,
    }

    return jsonify(
        {
            "order_id": order_id,
            "status": ORDERS[order_id]["status"],
            "product_id": product_id,
        }
    )


@app.get("/api/pay/check")
def pay_check():
    """
    결제 상태 확인
    입력(Query):
      - order_id: str
    출력(JSON):
      - order_id, status
    """
    order_id = str(request.args.get("order_id") or "").strip()

    if not order_id:
        return jsonify({"error": "order_id is required"}), 400

    order = ORDERS.get(order_id)
    if not order:
        return jsonify({"error": "order not found", "order_id": order_id}), 404

    return jsonify(
        {
            "order_id": order_id,
            "status": order.get("status"),
            "product_id": order.get("product_id"),
        }
    )


@app.get("/api/pay/download")
def pay_download():
    """
    다운로드 제공 (결제 완료된 주문만)
    입력(Query):
      - order_id: str
    동작:
      - 주문 상태가 paid면 해당 파일을 attachment로 전송
    """
    order_id = str(request.args.get("order_id") or "").strip()

    if not order_id:
        return jsonify({"error": "order_id is required"}), 400

    order = ORDERS.get(order_id)
    if not order:
        return jsonify({"error": "order not found", "order_id": order_id}), 404

    if order.get("status") != "paid":
        return jsonify({"error": "not paid", "status": order.get("status")}), 402

    download_file_path = str(order.get("download_file_path") or "")

    if not download_file_path or not os.path.exists(download_file_path):
        return (
            jsonify(
                {"error": "file not found", "download_file_path": download_file_path}
            ),
            404,
        )

    # 파일 다운로드 응답
    # as_attachment=True 로 브라우저가 파일 저장으로 처리
    return send_file(download_file_path, as_attachment=True)


if __name__ == "__main__":
    # 0.0.0.0 바인딩: 로컬 네트워크 테스트에도 유리 (원치 않으면 127.0.0.1로 변경)
    app.run(host="127.0.0.1", port=5000, debug=True)
