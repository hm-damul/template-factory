# -*- coding: utf-8 -*-
"""
generator_module.py (안정판)
- auto_pilot.py가 반드시 찾을 수 있도록 고정 엔트리: generate(topic)->str 제공
- 과거 ImportError 방지용: generator_module alias 제공
- f-string 중괄호 문제 방지: HTML은 format() 기반으로만 구성
"""

from __future__ import annotations

import html as _html
import re
import sys
import time


def _slugify(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "product"


def _escape(s: str) -> str:
    return _html.escape(s or "", quote=True)


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def generate(topic: str) -> str:
    title = _escape(topic.strip() or "Crypto Template")
    ts = _escape(_now())

    # CSS/JS 중괄호는 format()에서 {{ }}로 처리
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{title}</title>
  <style>
    :root {{
      --bg:#0b1020; --card:rgba(255,255,255,0.06); --text:#eaf0ff; --muted:rgba(234,240,255,0.72);
      --accent:#7c5cff; --accent2:#00d3a7; --shadow:0 18px 60px rgba(0,0,0,0.45); --radius:16px;
    }}
    *{{box-sizing:border-box}}
    body{{
      margin:0; font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial;
      background:radial-gradient(1200px 700px at 10% 10%, rgba(124,92,255,0.25), transparent 60%),
                 radial-gradient(900px 600px at 90% 20%, rgba(0,211,167,0.20), transparent 55%),
                 var(--bg);
      color:var(--text);
    }}
    .wrap{{max-width:1080px;margin:0 auto;padding:28px 18px 72px}}
    .card{{background:var(--card);border:1px solid rgba(255,255,255,0.10);border-radius:var(--radius);box-shadow:var(--shadow);padding:18px;backdrop-filter:blur(10px)}}
    .hero{{display:grid;grid-template-columns:1.2fr 0.8fr;gap:18px;margin-top:18px}}
    @media(max-width:900px){{.hero{{grid-template-columns:1fr}}}}
    .kicker{{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin:0 0 10px}}
    h1{{margin:0 0 10px;font-size:34px;line-height:1.15}}
    .sub{{margin:0 0 14px;color:var(--muted);line-height:1.55}}
    button{{cursor:pointer;border:none;border-radius:12px;padding:12px 14px;font-weight:800;color:#0b1020;background:linear-gradient(135deg,var(--accent),var(--accent2))}}
    button.secondary{{background:rgba(255,255,255,0.12);color:var(--text);border:1px solid rgba(255,255,255,0.14)}}
    .code{{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px;background:rgba(255,255,255,0.08);
          border:1px solid rgba(255,255,255,0.10);padding:10px;border-radius:12px;white-space:pre-wrap;color:rgba(234,240,255,0.90)}}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <p class="kicker">Product</p>
      <h1>{title}</h1>
      <p class="sub">Single-file template. Payment widget will be injected by pipeline.</p>
      <div class="code">[debug]\\ncreated_at: {ts}\\ntopic: {title}</div>
    </div>

    <div class="hero">
      <div class="card">
        <p class="kicker">UI Test</p>
        <p class="sub">This section ensures HTML buttons work before payment injection.</p>
        <button id="btnHello">Click Me</button>
        <div class="code" id="helloBox" style="margin-top:10px;">waiting...</div>
      </div>

      <div class="card">
        <p class="kicker">Checkout</p>
        <div id="payment-widget-placeholder" class="code">(payment widget will be injected here)</div>
      </div>
    </div>
  </div>

  <script>
    function qs(id) {{ return document.getElementById(id); }}
    var btn = qs("btnHello");
    var box = qs("helloBox");
    if (btn) {{
      btn.addEventListener("click", function() {{
        if (box) box.textContent = "OK: buttons are working.";
      }});
    }}
  </script>
</body>
</html>
""".format(title=title, ts=ts)


# 호환 엔트리(기존 코드가 어떤 이름을 호출해도 generate로 수렴)
def run(topic: str) -> str:
    return generate(topic)


def build(topic: str) -> str:
    return generate(topic)


def create(topic: str) -> str:
    return generate(topic)


def make(topic: str) -> str:
    return generate(topic)


def make_template(topic: str) -> str:
    return generate(topic)


# 과거 ImportError 패턴 방지용 alias
generator_module = sys.modules[__name__]
