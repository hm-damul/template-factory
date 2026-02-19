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
    price_usd: float = 19.9       # 가격 정보 추가

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

        # 이미 결제 로직(startPay 함수 등)이 존재하는지 확인하여 중복 삽입 방지
        # startPay(구버전) 또는 startCryptoPay(신버전) 중 하나라도 있으면 중단
        if 'async function startPay(' in html or 'async function startCryptoPay(' in html or 'id="catp-pay"' in html:
            # 이미 존재하면 스킵 (중복 삽입으로 인한 리다이렉트 무한 루프 방지)
            return

        widget_html = self._build_widget(product_id=product_id, price_usd=config.price_usd)

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

    def _build_widget(self, product_id: str, price_usd: float = 19.9) -> str:
        # JS에서 { }를 많이 쓰므로 f-string 대신 format을 쓰되, 중괄호는 {{ }}로 안전 처리
        # product_id만 format으로 삽입한다.
        return """
<!-- ======= PAYMENT WIDGET (injected) ======= -->
<div id="catp-pay" style="margin-top:14px;padding:14px;border:1px solid rgba(255,255,255,0.12);border-radius:14px;background:rgba(255,255,255,0.06);">
  <div style="font-weight:800;margin-bottom:8px;">Crypto Checkout (NOWPayments)</div>

  <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center;">
    <button id="catpPayBtn" style="cursor:pointer;border:none;border-radius:12px;padding:12px 14px;font-weight:800;background:linear-gradient(135deg,#7c5cff,#00d3a7);color:#0b1020;">
      결제하고 다운로드 (${price_usd:.2f})
    </button>

    <button id="catpCheckBtn" style="cursor:pointer;border:1px solid rgba(255,255,255,0.16);border-radius:12px;padding:12px 14px;font-weight:800;background:rgba(255,255,255,0.10);color:#eaf0ff;">
      결제 확인
    </button>
  </div>
  
  <div id="catpPayDetails" style="display:none;margin-top:14px;padding:14px;background:rgba(0,0,0,0.3);border:1px solid rgba(255,255,255,0.1);border-radius:10px;font-size:13px;">
    <div style="margin-bottom:8px;color:#aaa;font-weight:bold;">아래 주소로 정확한 금액을 전송하세요:</div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
        <span style="color:#00d3a7;font-weight:bold;font-size:16px;" id="catpPayAmount">0.00</span>
        <span style="color:#fff;font-weight:bold;" id="catpPayCurrency">USDT</span>
    </div>
    <div style="background:#111;padding:10px;border-radius:6px;word-break:break-all;user-select:all;color:#eaf0ff;font-family:monospace;border:1px dashed #444;cursor:pointer;" 
         onclick="navigator.clipboard.writeText(this.textContent);alert('주소가 복사되었습니다.');" 
         title="클릭하여 복사"
         id="catpPayAddress">Generating Address...</div>
    <div style="margin-top:8px;font-size:11px;color:#888;">* 입금 후 블록체인 승인까지 1~5분 소요될 수 있습니다.<br>* 이 페이지를 닫지 마세요. 자동 확인됩니다.</div>
  </div>

  <div id="catpStatus" style="margin-top:8px;font-size:14px;color:#aaa;"></div>
  <div id="catpDownloadArea" style="margin-top:8px;display:none;"></div>
</div>

<script>
(function(){{
  var PRODUCT_ID = "{product_id}";
  var PRICE_USD = {price_usd};
  var orderId = "";

  // 1. API Base URL 감지
  // "Live Mode" 강제 적용: 로컬/배포 환경 모두 Vercel Production URL 사용
  // 이로써 로컬 테스트에서도 실제 결제(NOWPayments)가 이루어지며, "Mock" 혼동을 방지합니다.
  var isLocal = false; 
  var API_BASE = "https://metapassiveincome-final.vercel.app";

  function qs(id) {{ return document.getElementById(id); }}
  function setStatus(msg) {{
    var el = qs("catpStatus");
    if (el) el.textContent = msg;
  }}
  function showDownload(url) {{
    var area = qs("catpDownloadArea");
    if (!area) return;
    area.style.display = "block";
    area.innerHTML = '<a href="' + (isLocal ? API_BASE : "") + url + '" target="_blank" style="color:#00d3a7;font-weight:bold;text-decoration:underline;font-size:16px;">[다운로드 링크 클릭]</a>';
    
    // Hide payment details on success
    var details = qs("catpPayDetails");
    if (details) details.style.display = "none";
    
    // Hide buttons
    if(qs("catpPayBtn")) qs("catpPayBtn").style.display = "none";
  }}

  // Expose to global for button clicks
  window.startCryptoPay = startCryptoPay;

  async function startCryptoPay(overridePrice) {{
    var finalPrice = PRICE_USD;
    if (overridePrice) {{
      // Parse "$19.90" -> 19.90
      var p = parseFloat(String(overridePrice).replace(/[^0-9.]/g, ""));
      if (!isNaN(p) && p > 0) finalPrice = p;
    }}

    setStatus("주문 생성 중... ($" + finalPrice + ")");
    try {{
      // Use GET to avoid 405 Method Not Allowed issues on some platforms
      var url = API_BASE + "/api/pay/start" + 
                "?product_id=" + encodeURIComponent(PRODUCT_ID) + 
                "&price_amount=" + encodeURIComponent(finalPrice);
      
      var res = await fetch(url, {{
        method: "GET",
        headers: {{ "Accept": "application/json" }}
      }});

      var data = await res.json().catch(function(){{ return {{}}; }});
      if (!res.ok) {{
        if (data.can_request) {{
          alert(data.message || \"상품이 일시적으로 삭제되었습니다. 워드프레스 댓글로 요청하시면 재생성해 드립니다!\");
          setStatus(\"재생성 요청 필요 (댓글로 문의)\");
        }} else {{
          setStatus(\"실패: \" + (data.error || (res.status + \" \" + res.statusText)));
        }}
        return;
      }}

      orderId = data.order_id || "";
      
      // Update Payment Details UI
      if (data.payment_address) {{
          var details = qs("catpPayDetails");
          if (details) {{
              details.style.display = "block";
              if(qs("catpPayAmount")) qs("catpPayAmount").textContent = data.pay_amount;
              if(qs("catpPayCurrency")) qs("catpPayCurrency").textContent = data.pay_currency;
              if(qs("catpPayAddress")) qs("catpPayAddress").textContent = data.payment_address;
          }}
          setStatus("입금 대기 중... (" + data.pay_currency + ")");
      }} else {{
          setStatus("주문 생성 완료 (order_id=" + orderId + "). 결제 확인 중...");
      }}

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
          showDownload("/downloads/" + PRODUCT_ID + ".zip");
        }}
        return;
      }}

      // If not paid
      if ((data.status || "") === "pending" || (data.status || "") === "waiting") {{
          setStatus("입금 확인 중... (" + (data.provider_status || "waiting") + ")");
      }} else {{
          setStatus("상태: " + (data.status || "unknown"));
      }}

      if (auto) {{
        // 폴링(최대 60회 * 3초 = 3분)
        var tries = 0;
        var timer = setInterval(async function() {{
          tries++;
          // Stop if element removed
          if (!qs("catpStatus")) {{ clearInterval(timer); return; }}
          
          if (tries > 60) {{
            clearInterval(timer);
            setStatus("시간 초과: 결제 완료를 확인하지 못했습니다. 수동으로 '결제 확인'을 눌러주세요.");
            return;
          }}
          await checkPay(false);
        }}, 3000);
      }}
    }} catch (e) {{
      setStatus("에러: " + (e && e.message ? e.message : String(e)));
    }}
  }}

  var payBtn = qs("catpPayBtn");
  var chkBtn = qs("catpCheckBtn");
  if (payBtn) payBtn.addEventListener("click", function() {{ startCryptoPay(null); }});
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
""".format(product_id=product_id, price_usd=price_usd)
