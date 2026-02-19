# -*- coding: utf-8 -*-
"""
preview_server.py
목적:
- outputs/ 아래 생성된 index.html들을 브라우저에서 쉽게 열어보게 하는 로컬 미리보기 서버
- /_list 에서 클릭 가능한 링크 목록 제공
- flask_cors 의존성 제거(초보자 환경에서 설치 이슈 방지)

실행:
  python preview_server.py
접속:
  http://127.0.0.1:8090/_list
"""

from __future__ import annotations

import sys

# Windows에서 cp949 인코딩 에러 방지
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

from pathlib import Path
from typing import Dict, List

from flask import Flask, Response, send_from_directory

app = Flask(__name__)

# 프로젝트 루트 = 이 파일이 있는 폴더
PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"


def _html_escape(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _collect_outputs() -> List[Dict[str, str]]:
    """
    outputs/<product_id>/index.html 목록 수집
    """
    items: List[Dict[str, str]] = []
    if not OUTPUTS_DIR.exists():
        return items

    for p in OUTPUTS_DIR.glob("*"):
        if not p.is_dir():
            continue
        index_html = p / "index.html"
        if index_html.exists():
            items.append(
                {
                    "product_id": p.name,
                    "rel_path": f"outputs/{p.name}/index.html",
                    "url": f"/outputs/{p.name}/index.html",
                }
            )

    # 최신 수정 파일이 위로 오게 정렬
    def _mtime(item: Dict[str, str]) -> float:
        try:
            return (OUTPUTS_DIR / item["product_id"] / "index.html").stat().st_mtime
        except Exception:
            return 0.0

    items.sort(key=_mtime, reverse=True)
    return items


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/_list")
def list_page() -> Response:
    items = _collect_outputs()

    rows = []
    for it in items:
        rows.append(f"""
            <div style="padding:10px;border:1px solid #ddd;border-radius:10px;margin:10px 0;">
              <div style="font-weight:700;">{_html_escape(it["product_id"])}</div>
              <div style="font-family:monospace;font-size:12px;color:#555;">{_html_escape(it["rel_path"])}</div>
              <div style="margin-top:8px;">
                <a href="{_html_escape(it["url"])}" target="_blank">Open</a>
              </div>
            </div>
            """)

    body = f"""
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8"/>
      <meta name="viewport" content="width=device-width, initial-scale=1"/>
      <title>Preview List</title>
      <style>
        body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; padding: 18px; }}
        .muted {{ color:#666; }}
        code {{ background:#f3f3f3; padding:2px 6px; border-radius:6px; }}
      </style>
    </head>
    <body>
      <h2>Preview List</h2>
      <p class="muted">
        outputs 폴더에서 <code>outputs/&lt;product_id&gt;/index.html</code> 을 찾아 링크로 보여줍니다.
      </p>
      <p class="muted">
        현재 outputs 경로: <code>{_html_escape(str(OUTPUTS_DIR))}</code>
      </p>
      {("".join(rows) if rows else "<p>outputs에 index.html이 없습니다. 먼저 <code>python auto_pilot.py</code>를 실행하세요.</p>")}
    </body>
    </html>
    """
    return Response(body, mimetype="text/html")


@app.get("/preview/<product_id>")
def preview_product(product_id: str):
    """
    /preview/<product_id> 로 접속 시 outputs/<product_id>/index.html 서빙
    """
    return send_from_directory(str(OUTPUTS_DIR / product_id), "index.html")

@app.get("/preview/<product_id>/<path:filename>")
def preview_product_assets(product_id: str, filename: str):
    """
    /preview/<product_id>/... 로 접속 시 해당 제품 폴더 내 파일 서빙 (assets 등)
    """
    return send_from_directory(str(OUTPUTS_DIR / product_id), filename)

@app.get("/outputs/<path:subpath>")
def serve_outputs(subpath: str):
    # outputs 폴더를 정적으로 서빙
    return send_from_directory(str(OUTPUTS_DIR), subpath)


if __name__ == "__main__":
    # Windows에서 포트 충돌 방지: host 127.0.0.1 고정
    # auto_mode_daemon.py와 포트 일치 (8088)
    app.run(host="127.0.0.1", port=8088, debug=False)
