# -*- coding: utf-8 -*-
"""
generator_module.py (프로덕션형 최소 안정판)

역할:
- auto_pilot.py가 호출하는 "고정 엔트리" generate(topic)->str 를 제공한다.
- 생성물은 index.html(랜딩페이지)로 사용되며, 동일한 결제/다운로드 계약을 사용한다.

중요 규칙:
- 브라우저는 /api/pay/start 를 반드시 POST로 호출해야 405를 피한다.
- 로컬에서는 payment_server(기본 5000)로 요청해야 하므로 API_BASE를 자동 설정한다.
- 배포(Vercel)에서는 same-origin("" 상대경로) 사용.

초보자 메모:
- f-string 중괄호 문제를 피하려고 HTML은 format() + {{ }} 를 사용한다.
"""

from __future__ import annotations

import html as _html  # HTML escape
import re  # slugify
import time  # timestamp


def _slugify(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "product"


def _escape(s: str) -> str:
    return _html.escape(s or "", quote=True)


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def generate(topic: str) -> str:
    """토픽을 받아 결제/다운로드가 연결된 랜딩 페이지 HTML을 생성한다."""
    title = _escape(topic.strip() or "Crypto Digital Product")
    ts = _escape(_now())
    slug = _escape(_slugify(topic))

    # format()을 사용하므로 CSS/JS 중괄호는 {{ }} 로 이스케이프
    return """<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{title}</title>
  <style>
    body {{ font-family: Arial, sans-serif; background:#0b0f14; color:#e7eef7; margin:0; }}
    .wrap {{ max-width: 920px; margin: 0 auto; padding: 24px; }}
    .card {{ background:#121a24; border:1px solid #1f2a3a; border-radius:14px; padding:18px; margin-top:16px; }}
    .btn {{ background:#3b82f6; border:none; color:white; padding:10px 14px; border-radius:10px; cursor:pointer; }}
    .btn:disabled {{ opacity:0.5; cursor:not-allowed; }}
    .muted {{ color:#93a4b8; font-size: 13px; }}
    a {{ color:#7dd3fc; }}
    code {{ background:#0b1220; padding:2px 6px; border-radius:6px; }}
    .row {{ display:flex; gap:12px; flex-wrap:wrap; }}
    .pill {{ display:inline-block; padding:4px 10px; border:1px solid #2a3a52; border-radius:999px; font-size:12px; color:#b9c7d8; }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <h1>{title}</h1>
    <div class=\"muted\">Generated at {ts} · slug: <code>{slug}</code></div>

    <div class=\"card\">
      <div class=\"row\">
        <span class=\"pill\">Crypto-only checkout</span>
        <span class=\"pill\">Instant download after paid</span>
        <span class=\"pill\">Privacy-first positioning</span>
      </div>
      <h2 style=\"margin-top:12px\">What you get</h2>
      <ul>
        <li><b>product.pdf</b> — structured guide/ebook</li>
        <li><b>bonus/</b> — checklists, prompts, scripts</li>
        <li><b>assets/</b> — simple icons</li>
        <li><b>promotions/</b> — ready-to-post marketing pack</li>
      </ul>

      <h2>Buy with crypto</h2>
      <p class=\"muted\">This page uses the same API contracts locally and on Vercel.</p>

      <!--PRICING_TIERS-->

      <!--PROOF_BLOCK-->

      <div class=\"row\">
        <button id=\"btnBuy\" class=\"btn\">Start Payment</button>
        <button id=\"btnCheck\" class=\"btn\" disabled>Check Status</button>
        <button id=\"btnDownload\" class=\"btn\" disabled>Download</button>
      </div>

      <pre id=\"log\" class=\"card\" style=\"white-space:pre-wrap; background:#0b1220\">[ready]</pre>
    </div>

    <div class=\"card\">
      <h3>Local links</h3>
      <div class=\"muted\">
        Preview list: <a href=\"http://127.0.0.1:8088/_list\" target=\"_blank\">http://127.0.0.1:8088/_list</a><br/>
        Local health: <a href=\"http://127.0.0.1:5000/health\" target=\"_blank\">http://127.0.0.1:5000/health</a>
      </div>
    </div>
  </div>

<script>
(function() {{
  // 로컬이면 payment_server로, 배포면 same-origin 사용
  const isLocal = (location.hostname === "127.0.0.1" || location.hostname === "localhost");
  const API_BASE = window.API_BASE || (isLocal ? "http://127.0.0.1:5000" : "");
  const productId = "{slug}"; // auto_pilot이 실제 product_id로 치환할 수 있음

  let orderId = null;

  let downloadUrl = null;

  const logEl = document.getElementById("log");
  const btnBuy = document.getElementById("btnBuy");
  const btnCheck = document.getElementById("btnCheck");
  const btnDownload = document.getElementById("btnDownload");

  function log(msg) {{
    logEl.textContent = String(msg);
  }}

  async function apiStart() {{
    log("[start] creating order...");
    const res = await fetch(API_BASE + "/api/pay/start", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ product_id: productId, amount: 29.0, currency: "usd" }})
    }});
    const data = await res.json();
    if (!res.ok) {{
      log("[error] " + JSON.stringify(data, null, 2));
      return;
    }}
    orderId = data.order_id;
    btnCheck.disabled = false;
    log("[created]\n" + JSON.stringify(data, null, 2));
    if (data.invoice_url) {{
      // NOWPayments 인보이스가 있으면 새 탭으로 열어줌
      window.open(data.invoice_url, "_blank");
    }}
  }}

  async function apiCheck() {{
    if (!orderId) return;
    log("[check] polling...");
    const res = await fetch(API_BASE + "/api/pay/check?order_id=" + encodeURIComponent(orderId), {{
      method: "GET"
    }});
    const data = await res.json();
    if (!res.ok) {{
      log("[error] " + JSON.stringify(data, null, 2));
      return;
    }}
    log("[status]\n" + JSON.stringify(data, null, 2));
    if (data.can_download) {{
      downloadUrl = data.download_url || (API_BASE + "/api/pay/download?order_id=" + encodeURIComponent(orderId));
      btnDownload.disabled = false;
    }}
  }}

  function apiDownload() {{
    if (!orderId) return;
    const url = downloadUrl || (API_BASE + "/api/pay/download?order_id=" + encodeURIComponent(orderId));
    window.location.href = url;
  }}

  btnBuy.addEventListener("click", apiStart);
  btnCheck.addEventListener("click", apiCheck);
  btnDownload.addEventListener("click", apiDownload);
}})();
</script>

</body>
</html>
""".format(title=title, ts=ts, slug=slug)
