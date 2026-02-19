# -*- coding: utf-8 -*-
"""
management_dashboard.py
목적:
- 로컬에서 "서버/파이프라인/로그/상품/주문"을 한 화면에서 제어하는 관리 대시보드(Flask)
- Windows 초보자 기준: 더블클릭 START.bat -> 이 대시보드만 실행하면 나머지는 버튼으로 제어

포트:
- http://127.0.0.1:8099

기능:
- 서버 제어: payment_server / preview_server 시작/중지
- 파이프라인 제어: auto_pilot 실행(백그라운드)
- 상태 표시: 실행 여부 + PID
- 로그 보기: tail(최근 N줄)
- 상품 관리: outputs/ 목록 + 미리보기 링크 + 삭제 + 재빌드(동일 topic)
- 주문 보기(로컬): backend/orders.json 읽기 + paid 강제 변경(테스트)

주의:
- "배포(Vercel)"와 무관하게, 로컬에서만 동작하는 관리자 UI 입니다.
- 프로세스 제어는 Windows 환경을 우선으로 구현했습니다(taskkill 사용).

실행:
  python management_dashboard.py
"""

from __future__ import annotations

import json  # JSON 읽기/쓰기
import os  # 경로/환경변수
import subprocess  # 프로세스 실행/종료
import sys  # 파이썬 실행 경로
import time  # 타임스탬프/폴링
from pathlib import Path  # 안전한 경로 처리
from typing import Any, Dict, List  # 타입 힌트

from flask import Flask, Response, jsonify, request  # Flask 기본 구성요소

# -----------------------------
# 기본 경로 설정(중요)
# -----------------------------

# 이 파일 기준으로 프로젝트 루트를 고정합니다(사용자가 cd 안 해도 됨).
PROJECT_ROOT: Path = (
    Path(__file__).resolve().parent
)  # .../MetaPassiveIncome_FIXED/MetaPassiveIncome_FIXED

# 출력물 폴더(outputs) 경로
OUTPUTS_DIR: Path = PROJECT_ROOT / "outputs"

# 로그 폴더(새로 생성)
LOG_DIR: Path = PROJECT_ROOT / "logs"

# 런타임 상태(PID 등) 저장 폴더
RUNTIME_DIR: Path = PROJECT_ROOT / ".runtime"

# 주문 저장 파일(backend/payment_server.py가 사용)
ORDERS_JSON: Path = PROJECT_ROOT / "backend" / "orders.json"

# 프로세스 PID 저장 파일
PID_FILE: Path = RUNTIME_DIR / "pids.json"


# -----------------------------
# 유틸 함수
# -----------------------------


def _ensure_dir(p: Path) -> None:
    """폴더가 없으면 생성합니다."""
    p.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default: Any) -> Any:
    """JSON을 안전하게 읽습니다(없으면 default)."""
    try:
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    """JSON을 안전하게 저장합니다(폴더 자동 생성)."""
    _ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _now_ts() -> str:
    """현재 시간을 사람이 읽기 쉬운 문자열로 반환합니다."""
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _tail_text_file(path: Path, max_lines: int = 200) -> str:
    """텍스트 파일의 마지막 max_lines 줄을 반환합니다."""
    try:
        if not path.exists():
            return ""
        # 파일을 통째로 읽어도 보통 로그는 크지 않지만, 안전을 위해 라인 단위로 제한합니다.
        with path.open("r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return "".join(lines[-max_lines:])
    except Exception as e:
        return f"[tail error] {e}"


def _is_pid_running(pid: int) -> bool:
    """PID가 실행 중인지 대략적으로 확인합니다(Windows)."""
    try:
        if pid <= 0:
            return False
        # tasklist로 PID 존재 여부 확인 (stdout에 pid가 나오면 실행 중)
        cp = subprocess.run(
            ["cmd", "/c", "tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True,
            text=True,
            check=False,
        )
        return str(pid) in (cp.stdout or "")
    except Exception:
        return False


def _kill_pid_tree(pid: int) -> bool:
    """Windows에서 PID 및 자식 프로세스를 강제 종료합니다."""
    try:
        if pid <= 0:
            return False
        subprocess.run(
            ["cmd", "/c", "taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            text=True,
            check=False,
        )
        return True
    except Exception:
        return False


def _load_pids() -> Dict[str, int]:
    """pids.json을 읽어 현재 PID 상태를 반환합니다."""
    data = _read_json(PID_FILE, {})
    # 타입 보정(문자열 -> int)
    out: Dict[str, int] = {}
    for k, v in (data or {}).items():
        try:
            out[str(k)] = int(v)
        except Exception:
            out[str(k)] = 0
    return out


def _save_pids(pids: Dict[str, int]) -> None:
    """pids.json을 저장합니다."""
    _write_json(PID_FILE, pids)


def _spawn_process(name: str, args: List[str], log_path: Path) -> int:
    """
    프로세스를 백그라운드로 실행하고 PID를 반환합니다.
    - cwd를 PROJECT_ROOT로 고정하여 cd 문제를 제거합니다.
    - stdout/stderr를 로그 파일로 리다이렉트합니다.
    """
    _ensure_dir(LOG_DIR)
    _ensure_dir(RUNTIME_DIR)

    # 로그 파일을 append 모드로 엽니다(기존 로그 유지).
    log_f = open(log_path, "a", encoding="utf-8")  # noqa: SIM115

    # Windows에서도 안정적으로 인코딩 로그가 나오도록 -u(언버퍼) 옵션을 사용합니다.
    proc = subprocess.Popen(
        args,
        cwd=str(PROJECT_ROOT),
        stdout=log_f,
        stderr=log_f,
        stdin=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        text=True,
    )

    # PID 반환
    return int(proc.pid)


def _start_if_not_running(key: str, args: List[str], log_name: str) -> Dict[str, Any]:
    """
    key에 해당하는 프로세스가 없으면 시작합니다.
    결과: {"ok": bool, "pid": int, "message": str}
    """
    pids = _load_pids()
    pid = int(pids.get(key, 0))

    if pid and _is_pid_running(pid):
        return {"ok": True, "pid": pid, "message": f"{key} already running"}

    log_path = LOG_DIR / log_name
    new_pid = _spawn_process(key, args=args, log_path=log_path)
    pids[key] = new_pid
    _save_pids(pids)

    return {"ok": True, "pid": new_pid, "message": f"{key} started"}


def _stop_if_running(key: str) -> Dict[str, Any]:
    """
    key에 해당하는 프로세스가 실행 중이면 종료합니다.
    결과: {"ok": bool, "pid": int, "message": str}
    """
    pids = _load_pids()
    pid = int(pids.get(key, 0))

    if not pid:
        return {"ok": True, "pid": 0, "message": f"{key} not running"}

    if not _is_pid_running(pid):
        pids[key] = 0
        _save_pids(pids)
        return {"ok": True, "pid": 0, "message": f"{key} already stopped"}

    _kill_pid_tree(pid)
    pids[key] = 0
    _save_pids(pids)
    return {"ok": True, "pid": 0, "message": f"{key} stopped"}


def _collect_products() -> List[Dict[str, Any]]:
    """
    outputs/ 안의 상품 목록을 수집합니다.
    기준:
    - outputs/<product_id>/index.html 존재
    - report.json 있으면 topic/created_at 등을 사용
    """
    items: List[Dict[str, Any]] = []
    if not OUTPUTS_DIR.exists():
        return items

    for p in OUTPUTS_DIR.iterdir():
        if not p.is_dir():
            continue

        index_html = p / "index.html"
        if not index_html.exists():
            continue

        report_path = p / "report.json"
        report = _read_json(report_path, {})

        # 생성일: report.created_at이 있으면 우선, 아니면 index.html mtime 사용
        created_at = report.get("created_at")
        if not created_at:
            try:
                created_at = time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(index_html.stat().st_mtime)
                )
            except Exception:
                created_at = ""

        items.append(
            {
                "product_id": p.name,
                "created_at": created_at,
                "topic": report.get("topic", ""),
                "preview_url": f"http://127.0.0.1:8088/outputs/{p.name}/index.html",
                "payment_test_url": f"http://127.0.0.1:8088/outputs/{p.name}/index.html",
            }
        )

    # 최신순 정렬(생성일 문자열이므로 mtime로 재정렬)
    def _mtime(item: Dict[str, Any]) -> float:
        try:
            return (OUTPUTS_DIR / item["product_id"] / "index.html").stat().st_mtime
        except Exception:
            return 0.0

    items.sort(key=_mtime, reverse=True)
    return items


def _delete_product(product_id: str) -> bool:
    """outputs/<product_id> 폴더를 삭제합니다."""
    try:
        target = OUTPUTS_DIR / product_id
        if not target.exists():
            return False
        # 안전장치: outputs 하위만 삭제 허용
        if OUTPUTS_DIR not in target.resolve().parents:
            return False
        import shutil as _shutil

        _shutil.rmtree(target, ignore_errors=True)
        return True
    except Exception:
        return False


# -----------------------------
# Flask 앱
# -----------------------------

app = Flask(__name__)  # Flask 인스턴스 생성


@app.get("/")
def home() -> Response:
    """대시보드 메인 HTML(단일 파일)."""
    html = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>MetaPassiveIncome Dashboard</title>
  <style>
    body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial;margin:0;background:#0b1020;color:#eaf0ff}}
    .wrap{{max-width:1200px;margin:0 auto;padding:18px}}
    .grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
    .card{{background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);border-radius:14px;padding:14px}}
    h1{{margin:0 0 12px 0;font-size:20px}}
    h2{{margin:0 0 10px 0;font-size:16px}}
    button{{background:#7c5cff;border:0;color:white;padding:8px 10px;border-radius:10px;cursor:pointer}}
    button.secondary{{background:#243049}}
    button.danger{{background:#c43b52}}
    input,select{{padding:8px;border-radius:10px;border:1px solid rgba(255,255,255,0.18);background:#101a33;color:#eaf0ff}}
    pre{{white-space:pre-wrap;background:#070a16;border:1px solid rgba(255,255,255,0.10);padding:10px;border-radius:12px;max-height:260px;overflow:auto}}
    .row{{display:flex;gap:8px;flex-wrap:wrap;align-items:center}}
    .muted{{color:rgba(234,240,255,0.7);font-size:12px}}
    table{{width:100%;border-collapse:collapse}}
    td,th{{border-bottom:1px solid rgba(255,255,255,0.10);padding:8px;text-align:left;font-size:13px}}
    a{{color:#00d3a7}}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>MetaPassiveIncome 로컬 관리 대시보드</h1>
    <div class="muted">프로젝트 루트: {PROJECT_ROOT.as_posix()}</div>

    <div class="grid" style="margin-top:14px;">
      <div class="card">
        <h2>서버 제어</h2>
        <div class="row">
          <button onclick="startPayment()">Start Payment Server</button>
          <button class="secondary" onclick="stopPayment()">Stop Payment Server</button>
          <button onclick="startPreview()">Start Preview Server</button>
          <button class="secondary" onclick="stopPreview()">Stop Preview Server</button>
        </div>
        <div class="row" style="margin-top:10px;">
          <button onclick="runAutoPilot()">Run auto_pilot</button>
          <input id="topic" placeholder="topic(비우면 자동)" style="min-width:260px;"/>
          <button class="secondary" onclick="refreshAll()">Refresh</button>
        </div>
        <div class="muted" id="statusBox" style="margin-top:10px;"></div>
      </div>

      <div class="card">
        <h2>로그 보기</h2>
        <div class="row">
          <select id="logSelect">
            <option value="payment.log">payment_server.log</option>
            <option value="preview.log">preview_server.log</option>
            <option value="auto_pilot.log">auto_pilot.log</option>
          </select>
          <button class="secondary" onclick="loadLog()">Load</button>
        </div>
        <pre id="logBox"></pre>
      </div>
    </div>

    <div class="grid" style="margin-top:14px;">
      <div class="card">
        <h2>상품 목록(outputs/)</h2>
        <div class="muted">미리보기 서버가 켜져 있어야 링크가 열립니다(Preview Server).</div>
        <div id="productsBox" style="margin-top:10px;"></div>
      </div>

      <div class="card">
        <h2>주문 목록(로컬 테스트)</h2>
        <div class="row">
          <button class="secondary" onclick="reloadOrders()">Reload</button>
        </div>
        <div id="ordersBox" style="margin-top:10px;"></div>
      </div>
    </div>

  </div>

<script>
async function apiPost(path, body) {{
  const res = await fetch(path, {{
    method: "POST",
    headers: {{"Content-Type":"application/json"}},
    body: JSON.stringify(body || {{}})
  }});
  return await res.json();
}}

async function apiGet(path) {{
  const res = await fetch(path);
  return await res.json();
}}

function esc(s) {{
  return (s||"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;");
}}

let selectedProducts = new Set();

function toggleAllProducts(checked) {{
  selectedProducts = new Set();
  const boxes = document.querySelectorAll(".bulkProduct");
  for (const cb of boxes) {{
    cb.checked = checked;
    if (checked) {{
      selectedProducts.add(cb.getAttribute("data-id"));
    }}
  }}
}}

function toggleOneProduct(cb) {{
  const id = cb.getAttribute("data-id");
  if (cb.checked) {{
    selectedProducts.add(id);
  }} else {{
    selectedProducts.delete(id);
  }}
}}

async function bulkApply() {{
  const ids = Array.from(selectedProducts);
  if (!ids.length) {{
    alert("선택된 상품이 없습니다.");
    return;
  }}
  const actionSel = document.getElementById("bulkAction");
  const action = actionSel ? actionSel.value : "delete";
  await apiPost("/api/products/bulk", {{action, product_ids: ids}});
  selectedProducts = new Set();
  await refreshAll();
}}
async function refreshAll() {{
  const st = await apiGet("/api/status");
  document.getElementById("statusBox").innerText =
    "payment_server PID=" + st.payment_server.pid + " running=" + st.payment_server.running + " | " +
    "preview_server PID=" + st.preview_server.pid + " running=" + st.preview_server.running + " | " +
    "auto_pilot PID=" + st.auto_pilot.pid + " running=" + st.auto_pilot.running + " | " +
    "time=" + st.time;

  selectedProducts = new Set();

  const products = await apiGet("/api/products");
  let html = "<table><thead><tr><th><input type='checkbox' onclick='toggleAllProducts(this.checked)'/></th><th>product_id</th><th>created</th><th>links</th><th>actions</th></tr></thead><tbody>";
  for (const p of products.items) {{
    html += "<tr>";
    html += "<td><input type='checkbox' class='bulkProduct' data-id='" + esc(p.product_id) + "' onchange='toggleOneProduct(this)'/></td>";
    html += "<td>" + esc(p.product_id) + "<div class='muted'>" + esc(p.topic||"") + "</div></td>";
    html += "<td>" + esc(p.created_at||"") + "</td>";
    html += "<td><a target='_blank' href='" + esc(p.preview_url) + "'>preview</a> / " +
            "<a target='_blank' href='" + esc(p.payment_test_url) + "'>payment test</a></td>";
    html += "<td class='row'>" +
            "<button class='danger' onclick='deleteProduct(\\"" + esc(p.product_id) + "\\")'>Delete</button>" +
            "<button class='secondary' onclick='rebuildProduct(\\"" + esc(p.product_id) + "\\")'>Rebuild</button>" +
            "</td>";
    html += "</tr>";
  }}
  html += "</tbody></table>";
  html += "<div class='row' style='margin-top:8px;'>";
  html += "<select id='bulkAction'><option value='delete'>Delete</option></select>";
  html += "<button class='secondary' onclick='bulkApply()'>Apply to selected</button>";
  html += "<span class='muted'>여러 상품을 한 번에 삭제</span>";
  html += "</div>";
  document.getElementById("productsBox").innerHTML = html;

  await reloadOrders();
}}

async function startPayment() {{
  await apiPost("/api/servers/payment/start", {{}});
  await refreshAll();
}}
async function stopPayment() {{
  await apiPost("/api/servers/payment/stop", {{}});
  await refreshAll();
}}
async function startPreview() {{
  await apiPost("/api/servers/preview/start", {{}});
  await refreshAll();
}}
async function stopPreview() {{
  await apiPost("/api/servers/preview/stop", {{}});
  await refreshAll();
}}
async function runAutoPilot() {{
  const topic = document.getElementById("topic").value || "";
  await apiPost("/api/pipeline/auto_pilot/run", {{topic}});
  await refreshAll();
}}
async function loadLog() {{
  const name = document.getElementById("logSelect").value;
  const data = await apiGet("/api/logs?name=" + encodeURIComponent(name));
  document.getElementById("logBox").innerText = data.text || "";
}}
async function deleteProduct(product_id) {{
  await apiPost("/api/products/delete", {{product_id}});
  await refreshAll();
}}
async function rebuildProduct(product_id) {{
  await apiPost("/api/products/rebuild", {{product_id}});
  await refreshAll();
}}

async function reloadOrders() {{
  const data = await apiGet("/api/orders");
  let html = "<table><thead><tr><th>order_id</th><th>product_id</th><th>status</th><th>actions</th></tr></thead><tbody>";
  for (const o of data.items) {{
    html += "<tr>";
    html += "<td>" + esc(o.order_id) + "<div class='muted'>" + esc(o.created_at||"") + "</div></td>";
    html += "<td>" + esc(o.product_id) + "</td>";
    html += "<td>" + esc(o.status) + "</td>";
    html += "<td class='row'>";
    if (o.status !== "paid") {{
      html += "<button onclick='markPaid(\\"" + esc(o.order_id) + "\\")'>Mark Paid</button>";
    }} else {{
      html += "<span class='muted'>paid</span>";
    }}
    html += "</td>";
    html += "</tr>";
  }}
  html += "</tbody></table>";
  document.getElementById("ordersBox").innerHTML = html;
}}
async function markPaid(order_id) {{
  await apiPost("/api/orders/mark_paid", {{order_id}});
  await reloadOrders();
}}

setInterval(refreshAll, 4000);
refreshAll();
</script>
</body>
</html>"""
    return Response(html, mimetype="text/html")


@app.get("/api/status")
def api_status() -> Response:
    """서버/파이프라인 PID 및 실행 여부를 반환합니다."""
    pids = _load_pids()

    def _info(key: str) -> Dict[str, Any]:
        pid = int(pids.get(key, 0))
        return {"pid": pid, "running": bool(pid and _is_pid_running(pid))}

    return jsonify(
        {
            "time": _now_ts(),
            "payment_server": _info("payment_server"),
            "preview_server": _info("preview_server"),
            "auto_pilot": _info("auto_pilot"),
        }
    )


@app.post("/api/servers/payment/start")
def api_start_payment() -> Response:
    """로컬 payment_server 시작."""
    # python -u backend/payment_server.py
    res = _start_if_not_running(
        key="payment_server",
        args=[
            sys.executable,
            "-u",
            str(PROJECT_ROOT / "backend" / "payment_server.py"),
        ],
        log_name="payment.log",
    )
    return jsonify(res)


@app.post("/api/servers/payment/stop")
def api_stop_payment() -> Response:
    """로컬 payment_server 중지."""
    res = _stop_if_running("payment_server")
    return jsonify(res)


@app.post("/api/servers/preview/start")
def api_start_preview() -> Response:
    """로컬 preview_server 시작."""
    res = _start_if_not_running(
        key="preview_server",
        args=[sys.executable, "-u", str(PROJECT_ROOT / "preview_server.py")],
        log_name="preview.log",
    )
    return jsonify(res)


@app.post("/api/servers/preview/stop")
def api_stop_preview() -> Response:
    """로컬 preview_server 중지."""
    res = _stop_if_running("preview_server")
    return jsonify(res)


@app.post("/api/pipeline/auto_pilot/run")
def api_run_auto_pilot() -> Response:
    """auto_pilot 실행(백그라운드)."""
    payload = request.get_json(silent=True) or {}
    topic = str(payload.get("topic", "")).strip()

    # topic을 환경변수로 전달하여 auto_pilot에서 읽게 합니다.
    env = os.environ.copy()
    if topic:
        env["CATP_TOPIC"] = topic

    # 로그 파일
    log_path = LOG_DIR / "auto_pilot.log"

    # 이미 실행 중이면 재실행하지 않음(중복 방지)
    pids = _load_pids()
    pid = int(pids.get("auto_pilot", 0))
    if pid and _is_pid_running(pid):
        return jsonify(
            {"ok": True, "pid": pid, "message": "auto_pilot already running"}
        )

    # 로그 append
    _ensure_dir(LOG_DIR)
    log_f = open(log_path, "a", encoding="utf-8")  # noqa: SIM115

    proc = subprocess.Popen(
        [sys.executable, "-u", str(PROJECT_ROOT / "auto_pilot.py")],
        cwd=str(PROJECT_ROOT),
        stdout=log_f,
        stderr=log_f,
        stdin=subprocess.DEVNULL,
        env=env,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        text=True,
    )

    pids["auto_pilot"] = int(proc.pid)
    _save_pids(pids)

    return jsonify({"ok": True, "pid": int(proc.pid), "message": "auto_pilot started"})


@app.get("/api/logs")
def api_logs() -> Response:
    """로그 파일 tail 반환."""
    name = str(request.args.get("name", "")).strip()
    # 화이트리스트로만 접근 허용(경로 공격 방지)
    allow = {
        "payment.log": LOG_DIR / "payment.log",
        "preview.log": LOG_DIR / "preview.log",
        "auto_pilot.log": LOG_DIR / "auto_pilot.log",
    }
    path = allow.get(name)
    if not path:
        return jsonify({"ok": False, "text": "", "message": "invalid log name"}), 400
    return jsonify({"ok": True, "text": _tail_text_file(path, max_lines=220)})


@app.get("/api/products")
def api_products() -> Response:
    """상품 목록 반환."""
    return jsonify({"ok": True, "items": _collect_products()})


@app.post("/api/products/delete")
def api_products_delete() -> Response:
    """상품 삭제."""
    payload = request.get_json(silent=True) or {}
    product_id = str(payload.get("product_id", "")).strip()
    if not product_id:
        return jsonify({"ok": False, "message": "product_id required"}), 400
    ok = _delete_product(product_id)
    return jsonify({"ok": ok})


@app.post("/api/products/bulk")
def api_products_bulk() -> Response:
    payload = request.get_json(silent=True) or {}
    action = str(payload.get("action", "")).strip()
    ids_raw = payload.get("product_ids") or []
    if not isinstance(ids_raw, list):
        return jsonify({"ok": False, "message": "product_ids must be list"}), 400
    product_ids = [str(x).strip() for x in ids_raw if str(x).strip()]
    if not product_ids:
        return jsonify({"ok": False, "message": "no product_ids"}), 400
    if action not in {"delete"}:
        return jsonify({"ok": False, "message": "unsupported action"}), 400
    results = []
    if action == "delete":
        for pid in product_ids:
            deleted = _delete_product(pid)
            results.append({"product_id": pid, "deleted": bool(deleted)})
    return jsonify({"ok": True, "action": action, "results": results})


@app.post("/api/products/rebuild")
def api_products_rebuild() -> Response:
    """상품 재빌드: report.json의 topic이 있으면 그 topic으로 auto_pilot 재실행."""
    payload = request.get_json(silent=True) or {}
    product_id = str(payload.get("product_id", "")).strip()
    if not product_id:
        return jsonify({"ok": False, "message": "product_id required"}), 400

    report_path = OUTPUTS_DIR / product_id / "report.json"
    report = _read_json(report_path, {})
    topic = str(report.get("topic", "")).strip()

    # topic이 없으면 product_id를 topic으로 사용(최소한 재생성은 가능)
    if not topic:
        topic = product_id.replace("-", " ")

    env = os.environ.copy()
    env["CATP_TOPIC"] = topic

    log_path = LOG_DIR / "auto_pilot.log"
    _ensure_dir(LOG_DIR)
    log_f = open(log_path, "a", encoding="utf-8")  # noqa: SIM115

    proc = subprocess.Popen(
        [sys.executable, "-u", str(PROJECT_ROOT / "auto_pilot.py")],
        cwd=str(PROJECT_ROOT),
        stdout=log_f,
        stderr=log_f,
        stdin=subprocess.DEVNULL,
        env=env,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        text=True,
    )

    pids = _load_pids()
    pids["auto_pilot"] = int(proc.pid)
    _save_pids(pids)

    return jsonify({"ok": True, "pid": int(proc.pid), "topic": topic})


@app.get("/api/orders")
def api_orders() -> Response:
    """로컬 주문 목록 반환(backend/orders.json)."""
    data = _read_json(ORDERS_JSON, {"orders": []})
    orders = data.get("orders", [])
    # 최신순 정렬
    try:
        orders = sorted(
            orders, key=lambda x: float(x.get("created_at_ts", 0.0)), reverse=True
        )
    except Exception:
        pass
    return jsonify({"ok": True, "items": orders})


@app.post("/api/orders/mark_paid")
def api_orders_mark_paid() -> Response:
    """주문을 paid로 변경(테스트용)."""
    payload = request.get_json(silent=True) or {}
    order_id = str(payload.get("order_id", "")).strip()
    if not order_id:
        return jsonify({"ok": False, "message": "order_id required"}), 400

    data = _read_json(ORDERS_JSON, {"orders": []})
    changed = False
    for o in data.get("orders", []):
        if str(o.get("order_id")) == order_id:
            o["status"] = "paid"
            o["paid_at"] = _now_ts()
            changed = True
            break

    _write_json(ORDERS_JSON, data)
    return jsonify({"ok": True, "changed": changed})


def main() -> None:
    """엔트리포인트."""
    _ensure_dir(LOG_DIR)
    _ensure_dir(RUNTIME_DIR)
    # 대시보드 기동
    app.run(host="127.0.0.1", port=8099, debug=False)


if __name__ == "__main__":
    main()
