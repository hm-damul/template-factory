# -*- coding: utf-8 -*-
"""
monetize_module.py
- 목적: outputs/<product_id>/index.html 에 결제+다운로드 위젯/스크립트를 자동 주입

- 동작 모드 자동 전환:
  - 로컬 프리뷰(127.0.0.1 / localhost) => payment_api_base = "http://127.0.0.1:5000"
  - 배포(Vercel 등)                    => payment_api_base = "" (same-origin 상대경로 /api)
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass


@dataclass
class PaymentInjectConfig:
    product_id: str
    download_file_path: str  # 로컬 테스트용(5000 서버에서 쓰는 값)
    payment_api_base: str = "http://127.0.0.1:5000"
    button_text: str = "결제하고 다운로드"
    amount_krw: int = 9900


class MonetizeModule:
    def inject_payment_logic(
        self, target_html_path: str, config: PaymentInjectConfig
    ) -> str:
        if not os.path.exists(target_html_path):
            raise FileNotFoundError(
                f"[monetize_module] target_html_path not found: {target_html_path}"
            )

        # 로컬 테스트 단계에서는 다운로드 파일이 필요
        # (배포에서는 public/downloads 로 제공하므로 이 파일은 로컬에서만 의미 있음)
        if not os.path.exists(config.download_file_path):
            raise FileNotFoundError(
                f"[monetize_module] download_file_path not found: {config.download_file_path}"
            )

        with open(target_html_path, "r", encoding="utf-8", errors="ignore") as f:
            original_html = f.read()

        # 중복 주입 방지
        if "data-mpi-payment-widget" in original_html:
            return original_html

        widget_html = self._build_payment_widget_html(config=config)
        script_html = self._build_payment_script_html(config=config)

        injected_html = self._inject_before_closing_tag(
            html=original_html,
            closing_tag="</body>",
            injection=widget_html + "\n" + script_html,
        )

        if injected_html == original_html:
            injected_html = self._inject_before_closing_tag(
                html=original_html,
                closing_tag="</html>",
                injection=widget_html + "\n" + script_html,
            )

        if injected_html == original_html:
            injected_html = (
                original_html + "\n" + widget_html + "\n" + script_html + "\n"
            )

        with open(target_html_path, "w", encoding="utf-8") as f:
            f.write(injected_html)

        return injected_html

    def _inject_before_closing_tag(
        self, html: str, closing_tag: str, injection: str
    ) -> str:
        match = re.search(re.escape(closing_tag), html, flags=re.IGNORECASE)
        if not match:
            return html
        idx = match.start()
        return html[:idx] + injection + "\n" + html[idx:]

    def _build_payment_widget_html(self, config: PaymentInjectConfig) -> str:
        return f"""
<!-- MPI_PAYMENT_WIDGET_START -->
<section data-mpi-payment-widget="1" style="max-width: 860px; margin: 24px auto; padding: 16px; border: 1px solid rgba(0,0,0,0.12); border-radius: 12px;">
  <div style="display: flex; flex-direction: column; gap: 10px;">
    <div style="font-size: 18px; font-weight: 700;">다운로드 받기</div>
    <div style="font-size: 14px; opacity: 0.8;">
      결제 완료 시 다운로드 링크가 활성화됩니다. (테스트 모드: 자동 결제 처리)
    </div>

    <div style="display:flex; gap: 10px; flex-wrap: wrap; align-items:center;">
      <button id="mpi-pay-btn"
              style="padding: 10px 14px; border-radius: 10px; border: 0; cursor: pointer;">
        {config.button_text} · {config.amount_krw:,} KRW
      </button>

      <button id="mpi-check-btn"
              style="padding: 10px 14px; border-radius: 10px; border: 1px solid rgba(0,0,0,0.15); background: transparent; cursor: pointer;">
        결제상태 확인
      </button>

      <span id="mpi-status" style="font-size: 13px; opacity: 0.85;">대기중</span>
    </div>

    <div>
      <a id="mpi-download-link"
         href="#"
         style="pointer-events: none; opacity: 0.45; text-decoration: underline;"
         download>
         결제 후 다운로드가 활성화됩니다
      </a>
    </div>

    <div style="font-size: 12px; opacity: 0.7;">
      product_id: <span id="mpi-product-id"></span> /
      order_id: <span id="mpi-order-id"></span>
    </div>
  </div>
</section>
<!-- MPI_PAYMENT_WIDGET_END -->
""".strip()

    def _build_payment_script_html(self, config: PaymentInjectConfig) -> str:
        cfg = {
            "product_id": config.product_id,
            "download_file_path": config.download_file_path,
            "payment_api_base": config.payment_api_base,
        }
        cfg_json = json.dumps(cfg, ensure_ascii=False)

        return f"""
<script>
/* MPI_PAYMENT_SCRIPT_START */
(function() {{
  const MPI_CFG = {cfg_json};

  // ---- 로컬/배포 자동 전환 ----
  // 로컬(프리뷰 서버)에서는 5000으로, 배포(Vercel)에서는 same-origin(/api)로 호출
  const isLocal = (location.hostname === "127.0.0.1" || location.hostname === "localhost");
  const API_BASE = isLocal ? "http://127.0.0.1:5000" : "";

  const payBtn = document.getElementById("mpi-pay-btn");
  const checkBtn = document.getElementById("mpi-check-btn");
  const statusEl = document.getElementById("mpi-status");
  const downloadLink = document.getElementById("mpi-download-link");
  const productIdEl = document.getElementById("mpi-product-id");
  const orderIdEl = document.getElementById("mpi-order-id");

  if (productIdEl) {{
    productIdEl.textContent = MPI_CFG.product_id || "";
  }}

  function setStatus(text) {{
    if (statusEl) statusEl.textContent = text;
  }}

  function enableDownload(url) {{
    downloadLink.href = url;
    downloadLink.style.pointerEvents = "auto";
    downloadLink.style.opacity = "1";
    downloadLink.textContent = "다운로드 시작 (결제 완료)";
  }}

  async function startPayment() {{
    try {{
      setStatus("주문 생성 중...");

      // 로컬: /api/pay/start (5000)
      // 배포: /api/pay/start (same-origin Vercel serverless)
      const resp = await fetch(API_BASE + "/api/pay/start", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{
          product_id: MPI_CFG.product_id,
          // 로컬 결제 서버(5000)에서는 필요
          download_file_path: MPI_CFG.download_file_path
        }})
      }});

      if (!resp.ok) {{
        const t = await resp.text();
        throw new Error("start failed: " + resp.status + " " + t);
      }}

      const data = await resp.json();

      if (orderIdEl) orderIdEl.textContent = data.order_id || "";

      // 테스트: paid 즉시 처리이므로 바로 다운로드 활성화
      if (data.status === "paid" && data.download_url) {{
        setStatus("결제 완료 ✅");
        enableDownload(data.download_url);
        return;
      }}

      await checkPayment(data.order_id);
    }} catch (err) {{
      console.error(err);
      setStatus("오류: " + (err && err.message ? err.message : String(err)));
    }}
  }}

  async function checkPayment(orderId) {{
    try {{
      if (!orderId) orderId = orderIdEl ? orderIdEl.textContent : "";
      if (!orderId) {{
        setStatus("order_id 없음 (먼저 결제를 시작하세요)");
        return;
      }}

      setStatus("결제 상태 확인 중...");

      // 배포 check.py는 product_id도 받으면 다운로드 링크 생성이 쉬움
      const url = API_BASE + "/api/pay/check?order_id=" + encodeURIComponent(orderId)
                + "&product_id=" + encodeURIComponent(MPI_CFG.product_id);

      const resp = await fetch(url, {{ method: "GET" }});
      if (!resp.ok) {{
        const t = await resp.text();
        throw new Error("check failed: " + resp.status + " " + t);
      }}

      const data = await resp.json();
      if (data.status === "paid" && data.download_url) {{
        setStatus("결제 완료 ✅");
        enableDownload(data.download_url);
      }} else {{
        setStatus("상태: " + String(data.status));
      }}
    }} catch (err) {{
      console.error(err);
      setStatus("오류: " + (err && err.message ? err.message : String(err)));
    }}
  }}

  if (payBtn) payBtn.addEventListener("click", startPayment);
  if (checkBtn) checkBtn.addEventListener("click", function() {{
    const oid = orderIdEl ? orderIdEl.textContent : "";
    checkPayment(oid);
  }});

  setStatus("대기중 (결제 버튼을 누르세요)");
}})();
/* MPI_PAYMENT_SCRIPT_END */
</script>
""".strip()
