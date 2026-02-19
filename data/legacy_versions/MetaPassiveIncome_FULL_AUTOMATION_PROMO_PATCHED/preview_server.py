# -*- coding: utf-8 -*-
"""
preview_server.py

목적:
- outputs/ 아래 생성된 제품 랜딩(index.html)을 로컬에서 미리보기 한다.
- /_list 에서 제품 목록을 보여준다.

실행:
  python preview_server.py
접속:
  http://127.0.0.1:8088/_list
"""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, abort, redirect, render_template_string, send_from_directory

app = Flask(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"


LIST_TEMPLATE = """<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\"/>
  <title>MetaPassiveIncome Preview</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; }
    a { color: #2563eb; }
    .card { border:1px solid #ddd; border-radius:10px; padding:12px; margin-top:10px; }
    .muted { color:#666; font-size: 13px; }
    code { background:#f3f4f6; padding:2px 6px; border-radius:6px; }
  </style>
</head>
<body>
  <h1>Outputs Preview</h1>
  <div class=\"muted\">Root: <code>{{root}}</code></div>
  {% for p in products %}
    <div class=\"card\">
      <div><b>{{p.product_id}}</b></div>
      <div class=\"muted\">
        <a href=\"/{{p.product_id}}/\" target=\"_blank\">Open landing</a>
        · <a href=\"/{{p.product_id}}/product.pdf\" target=\"_blank\">product.pdf</a>
        · <a href=\"/{{p.product_id}}/package.zip\" target=\"_blank\">package.zip</a>
      </div>
    </div>
  {% endfor %}
</body>
</html>
"""


@app.route("/_list")
def list_products():
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    products = []
    for d in sorted(OUTPUTS_DIR.iterdir()):
        if not d.is_dir():
            continue
        if (d / "index.html").exists():
            products.append({"product_id": d.name})
    return render_template_string(
        LIST_TEMPLATE, products=products, root=str(OUTPUTS_DIR)
    )


@app.route("/")
def root():
    return redirect("/_list")


@app.route("/<product_id>/")
def open_landing(product_id: str):
    d = OUTPUTS_DIR / product_id
    if not (d / "index.html").exists():
        abort(404)
    return send_from_directory(str(d), "index.html")


@app.route("/<product_id>/<path:filename>")
def open_asset(product_id: str, filename: str):
    d = OUTPUTS_DIR / product_id
    if not d.exists():
        abort(404)
    return send_from_directory(str(d), filename)


if __name__ == "__main__":
    port = int(os.getenv("PREVIEW_PORT", "8088"))
    app.run(host="127.0.0.1", port=port, debug=False)
