# -*- coding: utf-8 -*-
"""
dashboard_server.py

목적:
- 로컬 관리 대시보드(포트 8099)
- 서버 제어: Payment/Preview 시작/중지 + 상태/PID
- 파이프라인: auto_pilot 실행(batch N), product 재생성, 삭제
- 제품 관리: outputs 목록, 링크(미리보기/결제테스트/다운로드)
- 주문 뷰어: data/orders.json 조회 + 테스트용 paid 마킹
- 홍보: Publish 버튼(ready_to_publish.json 생성)

실행:
  python dashboard_server.py
접속:
  http://127.0.0.1:8099/
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask, jsonify, redirect, render_template_string, request, url_for

from order_store import FileOrderStore
from payment_api import mark_paid_testonly
from product_factory import ProductConfig, generate_one
from promotion_dispatcher import (
    dispatch_publish,
    load_channel_config,
    save_channel_config,
)
from promotion_factory import mark_ready_to_publish

app = Flask(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
PIDS_PATH = DATA_DIR / "pids.json"
AUTO_MODE_STATUS_PATH = DATA_DIR / "auto_mode_status.json"


def _atomic_write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _pids() -> Dict[str, Any]:
    return _read_json(PIDS_PATH, {})


def _set_pid(name: str, pid: int, cmd: List[str], log_file: str) -> None:
    p = _pids()
    p[name] = {
        "pid": int(pid),
        "cmd": cmd,
        "log_file": log_file,
        "started_at": _utc_iso(),
    }
    _atomic_write_json(PIDS_PATH, p)


def _clear_pid(name: str) -> None:
    p = _pids()
    if name in p:
        del p[name]
        _atomic_write_json(PIDS_PATH, p)


def _utc_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _is_windows() -> bool:
    return os.name == "nt"


def _kill_pid(pid: int) -> bool:
    """프로세스 종료(Windows/Unix 대응)."""
    try:
        if _is_windows():
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
            )
            return True
        else:
            os.kill(pid, 15)
            return True
    except Exception:
        return False


def _start_process(name: str, cmd: List[str]) -> Dict[str, Any]:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    log_path = LOGS_DIR / f"{name}.log"
    f = log_path.open("a", encoding="utf-8")
    try:
        p = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=f,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            shell=False,
        )
        _set_pid(name=name, pid=p.pid, cmd=cmd, log_file=str(log_path))
        return {"ok": True, "pid": p.pid, "log_file": str(log_path)}
    except Exception as e:
        f.close()
        return {"ok": False, "error": str(e)}


def _stop_process(name: str) -> Dict[str, Any]:
    info = _pids().get(name)
    if not info:
        return {"ok": True, "status": "not_running"}
    pid = int(info.get("pid", 0))
    ok = _kill_pid(pid)
    _clear_pid(name)
    return {"ok": ok, "pid": pid}


def _tail_log(path: Path, n: int = 200) -> str:
    if not path.exists():
        return "(log not found)"
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        return "\n".join(lines[-max(1, int(n)) :])
    except Exception:
        return "(failed to read log)"


def _list_products() -> List[Dict[str, Any]]:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for d in sorted(OUTPUTS_DIR.iterdir()):
        if not d.is_dir():
            continue
        item = {
            "product_id": d.name,
            "created_at": time.strftime(
                "%Y-%m-%d %H:%M:%S", time.gmtime(d.stat().st_mtime)
            ),
            "has_landing": (d / "index.html").exists(),
            "has_package": (d / "package.zip").exists(),
        }
        items.append(item)
    return items


def _orders_store() -> FileOrderStore:
    return FileOrderStore(DATA_DIR)


TEMPLATE = """<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\"/>
  <title>MetaPassiveIncome Dashboard</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; }
    .grid { display:grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .card { border:1px solid #ddd; border-radius:12px; padding:14px; }
    button { padding:8px 12px; border-radius:10px; border:1px solid #999; cursor:pointer; }
    input { padding:8px; border-radius:10px; border:1px solid #bbb; width: 100%; box-sizing: border-box; }
    .muted { color:#666; font-size: 13px; }
    code { background:#f3f4f6; padding:2px 6px; border-radius:6px; }
    table { width:100%; border-collapse: collapse; }
    th, td { border-bottom:1px solid #eee; padding:8px; text-align:left; font-size: 13px; }
    a { color:#2563eb; }
    pre { white-space: pre-wrap; background:#0b1220; color:#e7eef7; padding:10px; border-radius:10px; max-height:260px; overflow:auto; }
  </style>
</head>
<body>
  <h1>MetaPassiveIncome Dashboard</h1>
  <div class=\"muted\">Project root: <code>{{root}}</code></div>

  <div class=\"grid\">
    <div class=\"card\">
      <h2>Server Controls</h2>
      <div class=\"muted\">Payment: http://127.0.0.1:5000 · Preview: http://127.0.0.1:8088/_list</div>
      <p>
        <a href=\"/action/start_payment\"><button>Start Payment Server</button></a>
        <a href=\"/action/stop_payment\"><button>Stop Payment Server</button></a>
      </p>
      <p>
        <a href=\"/action/start_preview\"><button>Start Preview Server</button></a>
        <a href=\"/action/stop_preview\"><button>Stop Preview Server</button></a>
      </p>
      <div class=\"muted\">Running: {{pids}}</div>
    </div>

    <div class=\"card\">
      <h2>Pipeline Controls</h2>
      <div class="muted">auto_pilot은 1회 실행(배치) / Auto Mode는 주기적으로 자동 반복합니다.</div>
      <form method=\"post\" action=\"/action/run_autopilot\">
        <label class=\"muted\">Batch N</label>
        <input name=\"batch\" value=\"1\" />
        <label class=\"muted\">Optional topic (blank = auto)</label>
        <input name=\"topic\" value=\"\" />
        <p><button type=\"submit\">Run auto_pilot</button></p>
      </form>

      <form method=\"post\" action=\"/action/rebuild_product\">
        <label class=\"muted\">Rebuild by product_id</label>
        <input name=\"product_id\" value=\"\" />
        <label class=\"muted\">Topic (required)</label>
        <input name=\"topic\" value=\"\" />
        <p><button type=\"submit\">Rebuild Product</button></p>
      </form>
    </div>
  </div>

  <div class=\"card\" style=\"margin-top:16px\">
    <h2>Products</h2>
    <table>
      <thead>
        <tr>
          <th>product_id</th>
          <th>created_at(approx)</th>
          <th>links</th>
          <th>actions</th>
        </tr>
      </thead>
      <tbody>
        {% for p in products %}
        <tr>
          <td><code>{{p.product_id}}</code></td>
          <td>{{p.created_at}}</td>
          <td>
            {% if p.has_landing %}
              <a href=\"http://127.0.0.1:8088/{{p.product_id}}/\" target=\"_blank\">preview</a>
            {% endif %}
            {% if p.has_package %}
              · <a href=\"/download/{{p.product_id}}\" target=\"_blank\">package.zip</a>
            {% endif %}
          </td>
          <td>
            <a href=\"/action/publish/{{p.product_id}}\"><button>Publish</button></a>
            <a href=\"/action/test_publish/{{p.product_id}}\"><button>Test Publish</button></a>
            <a href=\"/action/delete_product/{{p.product_id}}\"><button>Delete</button></a>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  <div class=\"card\" style=\"margin-top:16px\">
    <h2>Orders (data/orders.json)</h2>
    <table>
      <thead>
        <tr><th>order_id</th><th>product_id</th><th>amount</th><th>currency</th><th>status</th><th>actions</th></tr>
      </thead>
      <tbody>
        {% for o in orders %}
        <tr>
          <td><code>{{o.order_id}}</code></td>
          <td><code>{{o.product_id}}</code></td>
          <td>{{o.amount}}</td>
          <td>{{o.currency}}</td>
          <td>{{o.status}}</td>
          <td>
            <form method=\"post\" action=\"/action/mark_paid\" style=\"display:inline\">
              <input type=\"hidden\" name=\"order_id\" value=\"{{o.order_id}}\"/>
              <button type=\"submit\">Mark Paid (test)</button>
            </form>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  <div class=\"grid\" style=\"margin-top:16px\">
    <div class=\"card\">
      <h2>Logs: payment</h2>
      <pre>{{log_payment}}</pre>
    </div>
    <div class=\"card\">
      <h2>Logs: preview</h2>
      <pre>{{log_preview}}</pre>
    </div>
  </div>

</body>
</html>
# """
# 
# 
# @app.route("/")
# def home():
#     pids = _pids()
#     products = _list_products()
# 
    # orders.json 로드
#     orders_raw = _orders_store().list_orders()
    # 화면용 간단 dict로
#     orders = []
#     for o in orders_raw[::-1][:200]:
#         orders.append(
#             {
#                 "order_id": o.get("order_id"),
#                 "product_id": o.get("product_id"),
#                 "amount": o.get("amount"),
#                 "currency": o.get("currency"),
#                 "status": o.get("status"),
#             }
#         )
# 
#     log_payment = _tail_log(LOGS_DIR / "payment.log")
#     log_preview = _tail_log(LOGS_DIR / "preview.log")
# 
#     auto_status = _read_json(AUTO_MODE_STATUS_PATH, {})
#     promo_cfg = load_channel_config()
#     return render_template_string(
#         TEMPLATE,
#         root=str(PROJECT_ROOT),
#         pids=pids,
#         products=products,
#         orders=orders,
#         log_payment=log_payment,
#         log_preview=log_preview,
#         auto_status=auto_status,
#         promo_cfg=promo_cfg,
#     )
# 
# 
# @app.route("/download/<product_id>")
# def download_package(product_id: str):
    # 대시보드는 로컬에서만 사용한다고 가정: 정적 파일로 직접 제공
#     pkg = OUTPUTS_DIR / product_id / "package.zip"
#     if not pkg.exists():
#         return jsonify({"error": "package_not_found", "product_id": product_id}), 404
    # 브라우저 다운로드를 위해 redirect로 파일 경로를 노출(로컬에서만)
#     return redirect(f"http://127.0.0.1:8088/{product_id}/package.zip")
# 
# 
# @app.route("/action/start_payment")
# def action_start_payment():
#     resp = _start_process("payment", [sys.executable, "backend/payment_server.py"])
#     return redirect(url_for("home"))
# 
# 
# @app.route("/action/stop_payment")
# def action_stop_payment():
#     _stop_process("payment")
#     return redirect(url_for("home"))
# 
# 
# @app.route("/action/start_preview")
# def action_start_preview():
#     resp = _start_process("preview", [sys.executable, "preview_server.py"])
#     return redirect(url_for("home"))
# 
# 
# @app.route("/action/stop_preview")
# def action_stop_preview():
#     _stop_process("preview")
#     return redirect(url_for("home"))
# 
# 
# @app.route("/action/stop_autopilot")
# def action_stop_autopilot():
#     _stop_process("autopilot")
#     return redirect(url_for("home"))
# 
# 
# @app.route("/action/save_promo_config", methods=["POST"])
# def save_promo_config_action():
#     """
    대시보드 폼에서 채널 설정 저장.
    tokens/urls 등 민감정보는 로컬 data/promo_channels.json에만 저장한다.
    """
    cfg = load_channel_config()

    # blog
    blog_mode = (request.form.get("blog_mode") or "none").strip().lower()
    blog_webhook_url = (request.form.get("blog_webhook_url") or "").strip()
    wp_api_url = (request.form.get("wp_api_url") or "").strip()
    wp_token = (request.form.get("wp_token") or "").strip()

    cfg["blog"] = {
        "mode": blog_mode,
        "webhook_url": blog_webhook_url,
        "wp_api_url": wp_api_url,
        "wp_token": wp_token,
    }

    # instagram / tiktok / youtube_shorts
    def _b(name: str) -> bool:
        return (request.form.get(name) or "").strip() in ["1", "true", "on", "yes"]

    cfg["instagram"] = {
        "enabled": _b("instagram_enabled"),
        "webhook_url": (request.form.get("instagram_webhook_url") or "").strip(),
    }
    cfg["tiktok"] = {
        "enabled": _b("tiktok_enabled"),
        "webhook_url": (request.form.get("tiktok_webhook_url") or "").strip(),
    }
    cfg["youtube_shorts"] = {
        "enabled": _b("youtube_enabled"),
        "webhook_url": (request.form.get("youtube_webhook_url") or "").strip(),
    }

    # safety
    cfg["dry_run"] = _b("dry_run")

    save_channel_config(cfg)
    return redirect(url_for("home"))


@app.route("/action/test_publish/<product_id>")
def test_publish(product_id: str):
    """
    현재 채널 설정으로 '발행'을 한 번 실행(가능하면 webhook/wordpress로 전송).
    키가 없으면 파일만 생성되고 no-op.
    """
    try:
        product_dir = OUTPUTS_DIR / product_id
        if not product_dir.exists():
            return jsonify({"ok": False, "error": "product_not_found"}), 404

        # ready 표시 + 채널 디스패치
        mark_ready_to_publish(product_dir=product_dir, product_id=product_id)
        res = dispatch_publish(product_id)
        return jsonify({"ok": True, "result": res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/action/start_auto_mode", methods=["POST"])
def action_start_auto_mode():
    interval = int(request.form.get("interval", "3600") or "3600")
    batch = int(request.form.get("auto_batch", "1") or "1")
    topic = str(request.form.get("auto_topic", "")).strip()
    deploy = (
        1
        if str(request.form.get("auto_deploy", "0")).strip()
        in ("1", "true", "on", "yes")
        else 0
    )
    publish = (
        1
        if str(request.form.get("auto_publish", "1")).strip()
        in ("1", "true", "on", "yes")
        else 0
    )

    cmd = [
        sys.executable,
        "auto_mode_daemon.py",
        "--interval",
        str(interval),
        "--batch",
        str(batch),
        "--deploy",
        str(deploy),
        "--publish",
        str(publish),
    ]
    if topic:
        cmd += ["--topic", topic]
    _start_process("auto_mode", cmd)
    return redirect(url_for("home"))


@app.route("/action/stop_auto_mode")
def action_stop_auto_mode():
    _stop_process("auto_mode")
    return redirect(url_for("home"))


@app.route("/action/run_autopilot", methods=["POST"])
def action_run_autopilot():
    batch = int(request.form.get("batch", "1") or "1")
    topic = str(request.form.get("topic", "")).strip()

    cmd = [sys.executable, "auto_pilot.py", "--batch", str(batch)]
    if topic:
        cmd += ["--topic", topic]

    # 대시보드는 "실행만" 하고, 로그는 파일로 남김
    _start_process("autopilot", cmd)
    return redirect(url_for("home"))


@app.route("/action/rebuild_product", methods=["POST"])
def action_rebuild_product():
    product_id = str(request.form.get("product_id", "")).strip()
    topic = str(request.form.get("topic", "")).strip()
    if not product_id or not topic:
        return jsonify({"error": "product_id_and_topic_required"}), 400

    # 기존 폴더 삭제 후 재생성
    d = OUTPUTS_DIR / product_id
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)

    meta = generate_one(
        ProductConfig(outputs_dir=OUTPUTS_DIR, topic=topic, product_id=product_id)
    )
    return redirect(url_for("home"))


@app.route("/action/delete_product/<product_id>")
def action_delete_product(product_id: str):
    d = OUTPUTS_DIR / product_id
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    return redirect(url_for("home"))


@app.route("/action/publish/<product_id>")
def action_publish(product_id: str):
    d = OUTPUTS_DIR / product_id
    if not d.exists():
        return jsonify({"error": "product_not_found", "product_id": product_id}), 404
    mark_ready_to_publish(product_dir=d, product_id=product_id)
    return redirect(url_for("home"))


@app.route("/action/mark_paid", methods=["POST"])
def action_mark_paid():
    order_id = str(request.form.get("order_id", "")).strip()
    if not order_id:
        return jsonify({"error": "order_id_required"}), 400
    mark_paid_testonly(project_root=PROJECT_ROOT, order_id=order_id)
    return redirect(url_for("home"))


def _auto_start_servers_if_enabled() -> None:
    """
    무인 운영 편의:
    - 기본값: payment/preview 서버를 자동 기동한다.
    - 끄려면: AUTO_START_SERVERS=0 환경변수 설정
    """
    flag = os.getenv("AUTO_START_SERVERS", "1").strip()
    if flag in ("0", "false", "False", "no", "NO"):
        return

    # 이미 PID가 있으면 건드리지 않는다(중복 실행 방지)
    p = _pids()

    if "payment" not in p:
        cmd = [sys.executable, "backend/payment_server.py"]
        _start_process("payment", cmd)

    if "preview" not in p:
        cmd = [sys.executable, "preview_server.py"]
        _start_process("preview", cmd)


if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", "8099"))
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    _auto_start_servers_if_enabled()
    app.run(host="127.0.0.1", port=port, debug=False)
