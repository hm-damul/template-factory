# -*- coding: utf-8 -*-
"""
monetize_module.py
목적:
- 생성된 HTML(index.html)에 "결제 시작 -> 결제 확인 폴링 -> 다운로드 링크 표시" 위젯을 주입한다.

중요(이번 수정):
- 과거 코드가 download_file_path가 "실제 존재하는 파일"이어야만 주입을 허용해서,
  auto_pilot 단계에서 FileNotFoundError로 크래시가 발생했다.
- 이제 download_file_path는 '옵션'이며, 비어 있어도 주입이 진행된다.
  (로컬은 payment_server가 /api/pay/download 로 제공, 배포는 /downloads/<product_id>/package.zip 제공)

로직:
- 로컬(host가 localhost/127.0.0.1이면) API_BASE = http://127.0.0.1:5000
- 배포(그 외) API_BASE = "" (same-origin)
- start: POST  {API_BASE}/api/pay/start  body: {product_id}
- check: GET   {API_BASE}/api/pay/check?order_id=...&product_id=...
- paid면 download_url을 표시하고, 로컬이면 API_BASE를 붙여 다운로드한다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class PaymentInjectConfig:
    product_id: str
    download_file_path: str = ""  # 옵션: 비어 있어도 됨


class MonetizeModule:
    def __init__(self) -> None:
        pass

    def inject_payment_logic(
        self, target_html_path: str, config: PaymentInjectConfig
    ) -> None:
        # 기본 검증: target_html만 있어야 함
        if not os.path.exists(target_html_path):
            raise FileNotFoundError(
                f"[monetize_module] target_html_path not found: {target_html_path}"
            )

        product_id = (config.product_id or "").strip()
        if not product_id:
            raise ValueError("[monetize_module] product_id is required")

        # HTML 읽기
        with open(target_html_path, "r", encoding="utf-8") as f:
            html = f.read()

        widget_html = self._build_widget(product_id=product_id)

        # 주입 위치 결정:
        # 1) placeholder가 있으면 그 자리에 교체
        placeholder = '<div id="payment-widget-placeholder"'
        if placeholder in html:
            # placeholder div를 찾아서 그 블록을 widget으로 치환
            # 초보자 환경에서 파싱 라이브러리 없이 안전하게: 단순 replace(첫 1회)
            # placeholder 자체가 div로 시작하고 끝날 수 있으므로, div 시작 위치만 찾고 그 뒤는 그대로 두되,
            # widget을 placeholder "바로 앞"에 삽입하는 방식으로 안정화한다.
            html = html.replace(placeholder, widget_html + "\n" + placeholder, 1)
        else:
            # 2) </body> 앞에 삽입
            if "</body>" in html.lower():
                # 대소문자 섞인 경우를 위해 단순 전략: 마지막 </body>를 찾는다
                lower = html.lower()
                idx = lower.rfind("</body>")
                if idx != -1:
                    html = html[:idx] + widget_html + "\n" + html[idx:]
                else:
                    html = html + "\n" + widget_html
            else:
                html = html + "\n" + widget_html

        # 저장
        with open(target_html_path, "w", encoding="utf-8") as f:
            f.write(html)

    def _build_widget(self, product_id: str) -> str:
        # JS에서 { }를 많이 쓰므로 f-string 대신 format을 쓰되, 중괄호는 {{ }}로 안전 처리
        # product_id만 format으로 삽입한다.
        return """
<!-- ======= PAYMENT WIDGET (injected) ======= -->
<div id="catp-pay" style="margin-top:14px;padding:14px;border:1px solid rgba(255,255,255,0.12);border-radius:14px;background:rgba(255,255,255,0.06);">
  <div style="font-weight:800;margin-bottom:8px;">Crypto Checkout</div>

  <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center;">
    <button id="catpPayBtn" style="cursor:pointer;border:none;border-radius:12px;padding:12px 14px;font-weight:800;background:linear-gradient(135deg,#7c5cff,#00d3a7);color:#0b1020;">
      결제하고 다운로드
    </button>

    <button id="catpCheckBtn" style="cursor:pointer;border:1px solid rgba(255,255,255,0.16);border-radius:12px;padding:12px 14px;font-weight:800;background:rgba(255,255,255,0.10);color:#eaf0ff;">
      결제 확인
    </button>
  </div>

  <div id="catpStatus" style="margin-top:10px;color:rgba(234,240,255,0.80);font-size:13px;line-height:1.5;">
    상태: 대기 중
  </div>

  <div id="catpDownload" style="margin-top:10px;display:none;">
    <a id="catpDownloadLink" href="#" style="display:inline-block;padding:10px 12px;border-radius:12px;background:rgba(0,211,167,0.14);border:1px solid rgba(0,211,167,0.35);color:#eaf0ff;text-decoration:none;font-weight:800;">
      다운로드 받기
    </a>
  </div>

  <div style="margin-top:10px;font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;font-size:12px;white-space:pre-wrap;color:rgba(234,240,255,0.75);">
product_id: {product_id}
  </div>
</div>

<script>
(function() {{
  var PRODUCT_ID = "{product_id}";

  function isLocalHost() {{
    try {{
      var h = window.location.hostname || "";
      return (h === "127.0.0.1" || h === "localhost");
    }} catch (e) {{
      return false;
    }}
  }}

  // 로컬이면 payment_server(5000)를 직접 호출, 배포면 same-origin
  var API_BASE = isLocalHost() ? "http://127.0.0.1:5000" : "";

  var orderId = "";

  function qs(id) {{ return document.getElementById(id); }}
  function setStatus(msg) {{
    var el = qs("catpStatus");
    if (el) el.textContent = "상태: " + msg;
  }}
  function showDownload(url) {{
    var wrap = qs("catpDownload");
    var a = qs("catpDownloadLink");
    if (!wrap || !a) return;

    // 로컬이면 /api/... 상대경로에 API_BASE를 붙여야 실제 다운로드가 된다.
    var finalUrl = url || "";
    if (API_BASE && finalUrl && finalUrl.indexOf("http") !== 0 && finalUrl[0] === "/") {{
      finalUrl = API_BASE + finalUrl;
    }}

    a.href = finalUrl || "#";
    wrap.style.display = "block";
  }}

  async function startPay() {{
    setStatus("주문 생성 중...");
    try {{
      var res = await fetch(API_BASE + "/api/pay/start", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ product_id: PRODUCT_ID }})
      }});

      var data = await res.json().catch(function(){{ return {{}}; }});
      if (!res.ok) {{
        setStatus("실패: " + (data.error || (res.status + " " + res.statusText)));
        return;
      }}

      orderId = data.order_id || "";
      setStatus("주문 생성 완료 (order_id=" + orderId + "). 결제 확인 중...");
      // 즉시 1회 check
      await checkPay(true);
    }} catch (e) {{
      setStatus("에러: " + (e && e.message ? e.message : String(e)));
    }}
  }}

  async function checkPay(auto) {{
    if (!orderId) {{
      setStatus("order_id가 없습니다. 먼저 '결제하고 다운로드'를 누르세요.");
      return;
    }}

    try {{
      var url = API_BASE + "/api/pay/check?order_id=" + encodeURIComponent(orderId) + "&product_id=" + encodeURIComponent(PRODUCT_ID);
      var res = await fetch(url, {{ method: "GET" }});
      var data = await res.json().catch(function(){{ return {{}}; }});
      if (!res.ok) {{
        setStatus("실패: " + (data.error || (res.status + " " + res.statusText)));
        return;
      }}

      if ((data.status || "") === "paid") {{
        setStatus("결제 완료 ✅ 다운로드 준비됨");
        if (data.download_url) {{
          showDownload(data.download_url);
        }} else {{
          // 배포 표준: downloads 경로
          showDownload("/downloads/" + PRODUCT_ID + "/package.zip");
        }}
        return;
      }}

      setStatus("미결제 (status=" + (data.status || "unknown") + ")");
      if (auto) {{
        // 폴링(최대 20회)
        var tries = 0;
        var timer = setInterval(async function() {{
          tries++;
          if (tries > 20) {{
            clearInterval(timer);
            setStatus("시간 초과: 결제 완료를 확인하지 못했습니다.");
            return;
          }}
          await checkPay(false);
        }}, 1500);
      }}
    }} catch (e) {{
      setStatus("에러: " + (e && e.message ? e.message : String(e)));
    }}
  }}

  var payBtn = qs("catpPayBtn");
  var chkBtn = qs("catpCheckBtn");
  if (payBtn) payBtn.addEventListener("click", startPay);
  if (chkBtn) chkBtn.addEventListener("click", function(){{ checkPay(false); }});

  // 디버그: API_BASE 노출
  try {{
    var ph = document.getElementById("payment-widget-placeholder");
    if (ph) {{
      ph.textContent = "payment_api_base=" + API_BASE + " (auto-detected)";
    }}
  }} catch (e) {{}}

}})();
</script>
<!-- ======= END PAYMENT WIDGET ======= -->
""".format(product_id=product_id)
