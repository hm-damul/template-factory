# -*- coding: utf-8 -*-
"""
backend/payment_server.py

목적:
- 로컬(개발)에서 결제 플로우를 실제 계약대로 테스트한다.
- NOWPayments 키가 있으면 실제 결제 생성/상태 조회를 사용한다.
- 키가 없으면 simulated 모드로 동작하되, API 계약은 동일하게 유지한다.

제공 API:
- GET  /health
- OPTIONS/POST /api/pay/start
- OPTIONS/GET  /api/pay/check
- OPTIONS/GET  /api/pay/download
- POST /api/pay/mark_paid   (테스트 전용, 대시보드에서 사용)

실행:
  python backend/payment_server.py
접속:
  http://127.0.0.1:5000/health
"""

from __future__ import annotations

import os  # 경로
from pathlib import Path  # 경로

from dotenv import load_dotenv  # env
from flask import Flask, Response, jsonify, request, send_file  # Flask

from payment_api import (  # 공통 로직, issue_download_token, get_order_status
    check_order,
    download_for_order,
    mark_paid_testonly,
    start_order,
)

app = Flask(__name__)


def _project_root() -> Path:
    """프로젝트 루트(이 파일 기준 상위 폴더)."""
    return Path(__file__).resolve().parent.parent


def _cors_headers() -> dict:
    """CORS 헤더(로컬 테스트용)."""
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    }


@app.after_request
def _after(resp: Response):
    for k, v in _cors_headers().items():
        resp.headers[k] = v
    return resp


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "service": "payment_server", "env": "local"})


@app.route("/api/pay/start", methods=["POST", "OPTIONS"])
def api_pay_start():
    if request.method == "OPTIONS":
        return ("", 204)

    data = request.get_json(silent=True) or {}
    product_id = str(data.get("product_id", "")).strip()
    amount = float(data.get("amount", 29.0))
    currency = str(data.get("currency", "usd")).lower().strip() or "usd"

    if not product_id:
        return jsonify({"error": "product_id_required"}), 400

    resp = start_order(
        project_root=_project_root(),
        product_id=product_id,
        amount=amount,
        currency=currency,
    )
    return jsonify(resp)


@app.route("/api/pay/check", methods=["GET", "OPTIONS"])
def api_pay_check():
    if request.method == "OPTIONS":
        return ("", 204)

    order_id = str(request.args.get("order_id", "")).strip()
    if not order_id:
        return jsonify({"error": "order_id_required"}), 400

    resp = check_order(project_root=_project_root(), order_id=order_id)
    return jsonify(resp)


@app.route("/api/pay/download", methods=["GET", "OPTIONS"])
def api_pay_download():
    if request.method == "OPTIONS":
        return ("", 204)

    order_id = str(request.args.get("order_id", "")).strip()
    if not order_id:
        return jsonify({"error": "order_id_required"}), 400

    info = download_for_order(project_root=_project_root(), order_id=order_id)
    if not info.get("ok"):
        return jsonify(info), int(info.get("status", 400))

    return send_file(
        info["package_path"],
        as_attachment=True,
        download_name=info.get("filename") or "package.zip",
        mimetype="application/zip",
    )


@app.route("/api/pay/mark_paid", methods=["POST", "OPTIONS"])
def api_mark_paid():
    """테스트 전용: order_id를 받아 paid로 바꾼다."""
    if request.method == "OPTIONS":
        return ("", 204)

    data = request.get_json(silent=True) or {}
    order_id = str(data.get("order_id", "")).strip()
    if not order_id:
        return jsonify({"error": "order_id_required"}), 400

    resp = mark_paid_testonly(project_root=_project_root(), order_id=order_id)
    code = 200 if resp.get("ok") else 404
    return jsonify(resp), code


@app.route("/api/pay/token", methods=["POST"])
def pay_token():
    """
    로컬용 토큰 발급:
    body: {"order_id": "..."}
    """
    data = request.get_json(silent=True) or {}
    order_id = str(data.get("order_id") or "").strip()
    if not order_id:
        return jsonify({"ok": False, "error": "order_id_required"}), 400

    st = get_order_status(project_root=PROJECT_ROOT, order_id=order_id)
    if not st.get("ok"):
        return jsonify(st), int(st.get("status", 400))
    if not st.get("paid"):
        return jsonify({"ok": False, "error": "not_paid"}), 403

    product_id = str(st.get("product_id") or "")
    token = issue_download_token(
        order_id=order_id, product_id=product_id, ttl_seconds=3600
    )
    return jsonify(
        {"ok": True, "token": token, "download_url": f"/api/pay/download?token={token}"}
    )


if __name__ == "__main__":
    # .env 로드(있으면)
    load_dotenv(dotenv_path=str(_project_root() / ".env"), override=False)
    load_dotenv(dotenv_path=str(_project_root() / ".env.local"), override=False)

    # 포트는 기본 5000, env로 변경 가능
    port = int(os.getenv("PAYMENT_PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=False)
