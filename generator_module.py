# generator_module.py
# 목적:
# - Vercel 정적 배포에서 "버튼 클릭/링크/모달/스크롤"이 반드시 동작하는 단일 HTML(내장 CSS+JS) 생성기
# - 생성물에 ``` 같은 코드펜스/백틱/잘못된 래핑이 절대 섞이지 않도록 sanitize/검증
# - 기존 auto_pilot이 찾는 공개 함수들(generate/run/build/create/make/make_template)을 모두 제공
#
# 변경(이번 수정):
# - (1) f-string 중괄호 문법 오류 방지: CSS/JS 블록은 반드시 {{ }} 형태 유지 (현재 파일은 정상)
# - (2) 경로 안전성 강화: os.makedirs("") 예외 방지
# - (3) product_id 폴더명 안전화(윈도우 금지 문자 제거/축약)
# - (4) 사용하지 않는 import 제거(가독성 개선)

from __future__ import annotations  # 파이썬 3.7+ 타입 힌트 forward ref를 안전하게 사용

import hashlib  # sha256
import json  # report.json 저장
import os  # 폴더/경로 처리
import re  # 문자열 검증(코드펜스 제거 등)
import time  # RUN_ID 생성용
from dataclasses import dataclass  # 설정 구조체
from typing import Any, Dict  # 타입 힌트

# -----------------------------
# 공통 유틸
# -----------------------------


def _now_id() -> str:
    # 실행 ID를 사람이 읽기 쉽게 생성
    return time.strftime("%Y%m%d-%H%M%S")


def _safe_dirname(name: str, fallback: str = "product") -> str:
    # 폴더명으로 쓰기 위험한 문자를 제거하고, 너무 길면 줄입니다(윈도우 호환).
    # 윈도우 금지: \ / : * ? " < > |
    name = (name or "").strip()  # None/공백 방지
    name = re.sub(r'[\\/:*?"<>|]+', "-", name)  # 금지 문자를 하이픈으로 치환
    name = re.sub(r"\s+", "-", name)  # 공백은 하이픈으로 통일
    name = re.sub(r"-{2,}", "-", name)  # 연속 하이픈 축약
    name = name.strip("-. ")  # 양끝 위험 문자 제거
    if not name:  # 비면 fallback 사용
        name = fallback
    # 너무 긴 경우(경로 길이/압축/배포 이슈 방지) 80자로 제한
    if len(name) > 80:
        name = name[:80].rstrip("-")
    return name


def _sha256_file(path: str) -> str:
    # 파일 sha256 계산
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _ensure_parent_dir(path: str) -> None:
    # 파일의 부모 폴더를 생성(부모가 없으면 아무 것도 하지 않음)
    parent = os.path.dirname(path)  # 부모 경로를 구함
    if parent:  # parent가 "" 이면 makedirs가 실패하므로 조건 처리
        os.makedirs(parent, exist_ok=True)  # 부모 폴더를 생성


def _write_text(path: str, text: str) -> None:
    # UTF-8로 텍스트 파일 저장
    _ensure_parent_dir(path)  # 부모 폴더를 보장
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _write_json(path: str, obj: Any) -> None:
    # JSON 저장
    _ensure_parent_dir(path)  # 부모 폴더를 보장
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _sanitize_html(html: str) -> str:
    """
    생성된 HTML에서 배포를 망치는 대표적인 흔적을 제거/차단.
    - ```html ... ``` 같은 코드펜스가 앞/뒤에 섞이면 브라우저가 문서를 이상하게 렌더링(스크린샷의 "<html" 텍스트 노출)
    - BOM/널문자 등도 제거
    """
    # 널문자 제거
    html = html.replace("\x00", "")

    # UTF-8 BOM이 문자열로 들어온 경우 제거
    html = html.lstrip("\ufeff")

    # 코드펜스 패턴이 들어오면 제거(특히 선두에 있을 때 치명적)
    # 1) 선두의 ```html / ``` 제거
    html = re.sub(r"^\s*```(?:html)?\s*\n", "", html, flags=re.IGNORECASE)
    # 2) 말미의 ``` 제거
    html = re.sub(r"\n\s*```\s*$", "", html)

    # 혹시 문서 중간에 코드펜스가 있으면(의도치 않게) 전부 제거
    html = re.sub(r"\n```(?:html)?\n", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"\n```\n", "\n", html)

    return html


def _validate_html(html: str) -> None:
    """
    배포 실패/버튼 미동작을 유발하는 요소를 강제 검증.
    - '문장 속 ```' 같은 정상 텍스트는 허용
    - "줄 시작 코드펜스" 형태만 차단 (진짜 마크다운 래핑에 가까움)
    """
    # 줄 시작에 ``` 가 나오면(마크다운 펜스 가능성) 실패 처리
    if re.search(r"(^|\n)\s*```", html):
        raise RuntimeError(
            "Generated HTML appears to contain markdown code fences at line start (```), aborting."
        )

    # 최소 골격 체크
    must_have = ["<!doctype html>", "<html", "<head", "<body", "</html>"]
    lower = html.lower()
    for token in must_have:
        if token not in lower:
            raise RuntimeError(f"Generated HTML missing required token: {token}")


# -----------------------------
# 랜딩 HTML 생성 (내장 CSS/JS)
# -----------------------------


def _render_landing_html(
    product_id: str,
    brand: str,
    headline: str,
    subheadline: str,
    primary_cta: str,
    secondary_cta: str,
) -> str:
#     """
#     단일 HTML 파일에 모든 기능 포함:
#     - 상단 네비 앵커 이동(#features/#pricing/#faq)
#     - 버튼 클릭 이벤트(Sign In, Get Started, Explore Plans, Learn More)
#     - 로그인 모달, 플랜 선택 모달
#     - 리드 수집(이메일) 데모: localStorage 저장
#     - URL hash 기반 라우팅(간단 SPA 느낌)
# 
#     주의:
#     - 아래 HTML은 f-string 입니다.
#     - CSS/JS의 중괄호는 반드시 {{ }} 로 써야 합니다(파이썬 f-string 규칙).
#     """

    # HTML 텍스트(주의: 절대로 ``` 같은 코드펜스를 넣지 말 것)
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="description" content="{subheadline}" />
  <title>{brand} | {headline}</title>

  <style>
    :root {{
      --bg: #070b12;
      --panel: rgba(255,255,255,0.06);
      --panel2: rgba(255,255,255,0.08);
      --text: rgba(255,255,255,0.92);
      --muted: rgba(255,255,255,0.68);
      --line: rgba(255,255,255,0.12);
      --glow: rgba(0,180,255,0.35);
      --accent: #00b4ff;
      --accent2: #22d3ee;
      --danger: #ff4d6d;
      --ok: #2ee59d;
      --radius: 16px;
    }}

    * {{
      box-sizing: border-box;
    }}

    html, body {{
      margin: 0;
      padding: 0;
      background: radial-gradient(1200px 800px at 70% 20%, rgba(0,180,255,0.18), transparent 55%),
                  radial-gradient(900px 600px at 25% 30%, rgba(34,211,238,0.14), transparent 55%),
                  var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji";
      line-height: 1.5;
      scroll-behavior: smooth;
    }}

    a {{
      color: inherit;
      text-decoration: none;
    }}

    .container {{
      max-width: 1100px;
      margin: 0 auto;
      padding: 24px;
    }}

    .nav {{
      position: sticky;
      top: 0;
      z-index: 50;
      backdrop-filter: blur(10px);
      background: linear-gradient(to bottom, rgba(7,11,18,0.88), rgba(7,11,18,0.55));
      border-bottom: 1px solid var(--line);
    }}

    .nav-inner {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 14px 24px;
      max-width: 1100px;
      margin: 0 auto;
    }}

    .brand {{
      display: flex;
      align-items: center;
      gap: 10px;
      font-weight: 800;
      letter-spacing: 0.2px;
    }}

    .logo {{
      width: 34px;
      height: 34px;
      border-radius: 12px;
      background: radial-gradient(circle at 30% 30%, rgba(34,211,238,0.9), rgba(0,180,255,0.3)),
                  rgba(255,255,255,0.06);
      box-shadow: 0 0 30px var(--glow);
      border: 1px solid rgba(255,255,255,0.16);
    }}

    .nav-links {{
      display: flex;
      align-items: center;
      gap: 16px;
      font-size: 14px;
      color: var(--muted);
    }}

    .nav-links a {{
      padding: 8px 10px;
      border-radius: 10px;
    }}

    .nav-links a:hover {{
      background: rgba(255,255,255,0.06);
      color: var(--text);
    }}

    .nav-actions {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}

    .btn {{
      border: 1px solid rgba(255,255,255,0.18);
      background: rgba(255,255,255,0.06);
      color: var(--text);
      padding: 10px 14px;
      border-radius: 12px;
      cursor: pointer;
      font-weight: 700;
      font-size: 14px;
      transition: transform 0.05s ease, background 0.2s ease, border 0.2s ease;
      user-select: none;
    }}

    .btn:hover {{
      background: rgba(255,255,255,0.10);
      border-color: rgba(255,255,255,0.26);
    }}

    .btn:active {{
      transform: translateY(1px);
    }}

    .btn-primary {{
      background: linear-gradient(135deg, rgba(0,180,255,0.95), rgba(34,211,238,0.85));
      border: 0;
      color: #001018;
      box-shadow: 0 12px 30px rgba(0,180,255,0.22);
    }}

    .hero {{
      padding: 64px 0 10px 0;
    }}

    .hero-grid {{
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 28px;
      align-items: center;
    }}

    @media (max-width: 920px) {{
      .hero-grid {{
        grid-template-columns: 1fr;
      }}
    }}

    .kicker {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 8px 12px;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--muted);
      background: rgba(255,255,255,0.04);
      font-size: 13px;
    }}

    .kicker-dot {{
      width: 8px;
      height: 8px;
      border-radius: 99px;
      background: var(--accent2);
      box-shadow: 0 0 16px rgba(34,211,238,0.45);
    }}

    h1 {{
      margin: 16px 0 10px 0;
      font-size: 46px;
      line-height: 1.08;
      letter-spacing: -0.6px;
    }}

    @media (max-width: 520px) {{
      h1 {{
        font-size: 36px;
      }}
    }}

    .sub {{
      margin: 0;
      color: var(--muted);
      font-size: 16px;
      max-width: 60ch;
    }}

    .hero-actions {{
      margin-top: 22px;
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
    }}

    .panel {{
      background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.03));
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 18px;
      box-shadow: 0 24px 60px rgba(0,0,0,0.35);
    }}

    .panel h3 {{
      margin: 0 0 10px 0;
      font-size: 16px;
    }}

    .panel p {{
      margin: 0;
      color: var(--muted);
      font-size: 14px;
    }}

    .stats {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 10px;
      margin-top: 14px;
    }}

    .stat {{
      padding: 12px;
      border-radius: 14px;
      background: rgba(255,255,255,0.05);
      border: 1px solid rgba(255,255,255,0.10);
    }}

    .stat strong {{
      display: block;
      font-size: 15px;
    }}

    .stat span {{
      display: block;
      font-size: 12px;
      color: var(--muted);
      margin-top: 4px;
    }}

    section {{
      padding: 36px 0;
    }}

    .section-title {{
      font-size: 22px;
      margin: 0 0 12px 0;
      letter-spacing: -0.2px;
    }}

    .grid3 {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 14px;
    }}

    @media (max-width: 920px) {{
      .grid3 {{
        grid-template-columns: 1fr;
      }}
    }}

    .card {{
      padding: 16px;
      border-radius: var(--radius);
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.05);
    }}

    .card h4 {{
      margin: 0 0 8px 0;
      font-size: 15px;
    }}

    .card p {{
      margin: 0;
      color: var(--muted);
      font-size: 13px;
    }}

    .pricing {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 14px;
    }}

    @media (max-width: 920px) {{
      .pricing {{
        grid-template-columns: 1fr;
      }}
    }}

    .price {{
      font-size: 28px;
      margin: 10px 0 8px 0;
      letter-spacing: -0.4px;
    }}

    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      color: rgba(255,255,255,0.75);
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid rgba(255,255,255,0.14);
      background: rgba(255,255,255,0.04);
    }}

    .badge .pill {{
      width: 8px;
      height: 8px;
      border-radius: 99px;
      background: var(--ok);
      box-shadow: 0 0 18px rgba(46,229,157,0.35);
    }}

    .list {{
      margin: 10px 0 0 0;
      padding: 0;
      list-style: none;
      color: var(--muted);
      font-size: 13px;
    }}

    .list li {{
      padding: 6px 0;
      border-top: 1px dashed rgba(255,255,255,0.12);
    }}

    .faq {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
    }}

    @media (max-width: 920px) {{
      .faq {{
        grid-template-columns: 1fr;
      }}
    }}

    footer {{
      padding: 28px 0 46px 0;
      color: var(--muted);
      border-top: 1px solid var(--line);
      margin-top: 26px;
      font-size: 13px;
    }}

    .row {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 12px;
    }}

    /* 모달 removed */
    .toast {{
      position: fixed;
      right: 14px;
      bottom: 14px;
      background: rgba(10,14,22,0.92);
      border: 1px solid rgba(255,255,255,0.14);
      padding: 10px 12px;
      border-radius: 14px;
      color: var(--text);
      display: none;
      z-index: 999;
      max-width: 360px;
      box-shadow: 0 24px 80px rgba(0,0,0,0.5);
      font-size: 13px;
    }}
  </style>
</head>

<body data-product-id="{product_id}">
  <div class="nav">
    <div class="nav-inner">
      <div class="brand">
        <div class="logo" aria-hidden="true"></div>
        <div>{brand}</div>
      </div>

      <div class="nav-links" aria-label="Primary">
        <a href="#features" data-action="nav" data-target="#features">Features</a>
        <a href="#pricing" data-action="nav" data-target="#pricing">Pricing</a>
        <a href="#faq" data-action="nav" data-target="#faq">FAQ</a>
      </div>

      <div class="nav-actions">
        <button class="btn" data-action="open-login">{secondary_cta}</button>
        <button class="btn btn-primary" data-action="open-plans">{primary_cta}</button>
      </div>
    </div>
  </div>

  <main class="container">
    <div class="hero">
      <div class="hero-grid">
        <div>
          <div class="kicker">
            <span class="kicker-dot"></span>
            <span>Web3-ready SaaS landing (single-file) • Vercel static friendly</span>
          </div>
          <h1>{headline}</h1>
          <p class="sub">{subheadline}</p>

          <div class="hero-actions">
            <button class="btn btn-primary" data-action="open-plans">Explore Plans</button>
            <button class="btn" data-action="scroll" data-target="#features">Learn More</button>
          </div>

          <div style="margin-top:14px; color: rgba(255,255,255,0.62); font-size: 13px;">
            Secure payment processing via NOWPayments.
          </div>
        </div>

        <div class="panel" aria-label="Status panel">
          <h3>System Status</h3>
          <p>Buttons are wired by a data-action router (no framework). If a click does nothing, your HTML was wrapped/escaped.</p>

          <div class="stats">
            <div class="stat">
              <strong id="stat-leads">0</strong>
              <span>Leads captured</span>
            </div>
            <div class="stat">
              <strong id="stat-plan">None</strong>
              <span>Selected plan</span>
            </div>
            <div class="stat">
              <strong id="stat-auth">Guest</strong>
              <span>Auth state</span>
            </div>
          </div>

          <div class="row">
            <button class="btn" data-action="open-login">Sign In</button>
            <button class="btn" data-action="open-plans">Get Started</button>
            <button class="btn" data-action="reset-demo">Reset</button>
          </div>

          <div class="hint" id="debug-hint"></div>
        </div>
      </div>
    </div>

    <section id="features">
      <h2 class="section-title">Features</h2>
      <div class="grid3">
        <div class="card">
          <h4>Wallet-ready checkout</h4>
          <p>Designed for crypto-wallet users. Next step: invoice creation + webhook → fulfillment.</p>
        </div>
        <div class="card">
          <h4>One-file deploy</h4>
          <p>No build step required. Works on Vercel static hosting. No missing JS bundles.</p>
        </div>
        <div class="card">
          <h4>Action router</h4>
          <p>All buttons use <code>data-action</code>. Easy to extend with payment + download gating.</p>
        </div>
      </div>
    </section>

    <section id="pricing">
      <h2 class="section-title">Pricing</h2>
      <div class="pricing">
        <div class="card">
          <div class="badge"><span class="pill"></span><span>Starter</span></div>
          <div class="price">$19<span style="font-size:14px; color: var(--muted);">/mo</span></div>
          <p class="sub" style="font-size:13px;">For early users testing your checkout.</p>
          <ul class="list">
            <li>Basic analytics</li>
            <li>Email lead capture</li>
            <li>Community support</li>
          </ul>
          <div class="row">
            <button class="btn btn-primary" data-action="choose-plan" data-plan="Starter">Choose Starter</button>
          </div>
        </div>

        <div class="card" style="border-color: rgba(0,180,255,0.38); box-shadow: 0 24px 80px rgba(0,180,255,0.12);">
          <div class="badge"><span class="pill" style="background: var(--accent2); box-shadow: 0 0 18px rgba(34,211,238,0.35);"></span><span>Pro</span></div>
          <div class="price">$49<span style="font-size:14px; color: var(--muted);">/mo</span></div>
          <p class="sub" style="font-size:13px;">For sales-focused crypto products.</p>
          <ul class="list">
            <li>Plan gating ready</li>
            <li>Webhook endpoint scaffold (next)</li>
            <li>Priority support</li>
          </ul>
          <div class="row">
            <button class="btn btn-primary" data-action="choose-plan" data-plan="Pro">Choose Pro</button>
          </div>
        </div>

        <div class="card">
          <div class="badge"><span class="pill" style="background: #ffb703; box-shadow: 0 0 18px rgba(255,183,3,0.25);"></span><span>Enterprise</span></div>
          <div class="price">$199<span style="font-size:14px; color: var(--muted);">/mo</span></div>
          <p class="sub" style="font-size:13px;">For teams requiring custom flows.</p>
          <ul class="list">
            <li>Custom domains</li>
            <li>Dedicated onboarding</li>
            <li>SLA support</li>
          </ul>
          <div class="row">
            <button class="btn btn-primary" data-action="choose-plan" data-plan="Enterprise">Choose Enterprise</button>
          </div>
        </div>
      </div>
    </section>

    <section id="faq">
      <h2 class="section-title">FAQ</h2>
      <div class="faq">
        <div class="card">
          <h4>Why are buttons sometimes unresponsive?</h4>
          <p>If the HTML file is wrapped in markdown fences (```html) or served escaped, the DOM differs and scripts may not run as expected. This generator strips fences and validates output.</p>
        </div>
        <div class="card">
          <h4>Where does payment integration go?</h4>
          <p>Next module: serverless function (Vercel) → create invoice → receive webhook → unlock download/email. This HTML already supports gating hooks.</p>
        </div>
      </div>
    </section>

    <footer>
      <div>Product ID: <strong>{product_id}</strong></div>
      <div style="margin-top:6px;">© {brand}. Single-file landing for fast iteration.</div>
    </footer>
  </main>

  <!-- Toast -->
  <div class="toast" id="toast"></div>

  <script>
    (function() {{
      "use strict";

      // ----- 작은 유틸 -----
      function qs(sel) {{ return document.querySelector(sel); }}
      function qsa(sel) {{ return Array.from(document.querySelectorAll(sel)); }}

      function showToast(msg) {{
        var t = qs("#toast");
        if (!t) return;
        t.textContent = msg;
        t.style.display = "block";
        clearTimeout(window.__toastTimer);
        window.__toastTimer = setTimeout(function() {{
          t.style.display = "none";
        }}, 2200);
      }}

      function scrollToTarget(hash) {{
        try {{
          var el = qs(hash);
          if (el) {{
            el.scrollIntoView({{ behavior: "smooth", block: "start" }});
          }}
        }} catch (e) {{}}
      }}

      // ----- 로컬 저장 (데모) -----
      var productId = document.body.getAttribute("data-product-id") || "product";
      var KEY_LEADS = productId + ":leads";
      var KEY_PLAN  = productId + ":plan";
      var KEY_AUTH  = productId + ":auth";
      var KEY_PRICE = productId + ":price";

      async function startPay(plan) {{
        var rawPrice = "{product_price}";
        var stored = localStorage.getItem(KEY_PRICE);
        if (stored) rawPrice = stored;

        showToast("Redirecting to secure checkout...");
        setTimeout(function() {{
            var url = "checkout.html?price=" + encodeURIComponent(rawPrice);
            window.location.href = url;
        }}, 500);
      }}

      function readJson(key, fallback) {{
        try {{
          var v = localStorage.getItem(key);
          if (!v) return fallback;
          return JSON.parse(v);
        }} catch (e) {{
          return fallback;
        }}
      }}

      function writeJson(key, obj) {{
        localStorage.setItem(key, JSON.stringify(obj));
      }}

      // ----- 액션 라우터 -----
      var actions = {{
        "nav": function(el) {{
          var target = el.getAttribute("data-target") || el.getAttribute("href") || "#features";
          if (target.startsWith("#")) {{
            scrollToTarget(target);
          }}
        }},

        "scroll": function(el) {{
          var target = el.getAttribute("data-target") || "#features";
          if (target.startsWith("#")) {{
            scrollToTarget(target);
          }}
        }},

        "open-login": function() {{
          startPay("SignIn");
        }},

        "open-plans": function() {{
          var plan = localStorage.getItem(KEY_PLAN) || "Premium";
          startPay(plan);
        }},

        "choose-plan": function(el) {{
          var plan = el.getAttribute("data-plan") || "Starter";
          var price = el.getAttribute("data-price") || "$19";
          localStorage.setItem(KEY_PLAN, plan);
          localStorage.setItem(KEY_PRICE, price);

          showToast("Plan selected: " + plan + " (" + price + ")");
          startPay(plan);
        }},

        "reset-demo": function() {{
          localStorage.removeItem(KEY_LEADS);
          localStorage.removeItem(KEY_PLAN);
          localStorage.removeItem(KEY_AUTH);
          showToast("Reset.");
        }}
      }};

      function handleClick(e) {{
        var el = e.target;
        // 버튼 안쪽 span 클릭 등 대비: data-action 가진 조상까지 탐색
        while (el && el !== document.body) {{
          var act = el.getAttribute && el.getAttribute("data-action");
          if (act) {{
            e.preventDefault();
            var fn = actions[act];
            if (fn) {{
              fn(el);
            }} else {{
              showToast("Unknown action: " + act);
            }}
            return;
          }}
          el = el.parentNode;
        }}
      }}

      // ----- 해시 라우팅(단순) -----
      function onHashChange() {{
        var h = location.hash || "";
        if (h && h.startsWith("#")) {{
          if (qs(h)) {{
            scrollToTarget(h);
          }}
        }}
      }}

      // ----- 초기 바인딩 -----
      document.addEventListener("click", handleClick);
      window.addEventListener("hashchange", onHashChange);

      // 초기 해시 처리
      onHashChange();

      // showToast("JS loaded.");
    }})();
  </script>
</body>
</html>
"""
    return html
# 
# 
# -----------------------------
# 설정/팩토리
# -----------------------------


def _render_checkout_html(
    product_id: str,
    product_price: str,
    product_title: str,
    brand: str
) -> str:
    """정적 결제 페이지(checkout.html) 생성. Payment Server와 통신."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Checkout - {brand}</title>
    <style>
        body {{
            font-family: 'Inter', system-ui, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
        }}
        .checkout-container {{
            background: #1e293b;
            padding: 2rem;
            border-radius: 1rem;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            width: 100%;
            max-width: 400px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        h1 {{ margin-bottom: 0.5rem; font-size: 1.5rem; color: #fff; }}
        .price {{ font-size: 2.5rem; font-weight: 700; color: #38bdf8; margin: 1rem 0; }}
        .product-name {{ color: #94a3b8; margin-bottom: 2rem; }}
        .btn {{
            background: #38bdf8;
            color: #0f172a;
            border: none;
            padding: 1rem 2rem;
            border-radius: 0.5rem;
            font-weight: 600;
            font-size: 1.1rem;
            cursor: pointer;
            width: 100%;
            transition: opacity 0.2s;
        }}
        .btn:hover {{ opacity: 0.9; }}
        .btn:disabled {{ opacity: 0.5; cursor: not-allowed; }}
        .error {{ color: #ef4444; margin-top: 1rem; font-size: 0.9rem; display: none; }}
        .back-link {{ display: block; margin-top: 1.5rem; color: #94a3b8; text-decoration: none; font-size: 0.9rem; }}
        .back-link:hover {{ color: #fff; }}
    </style>
</head>
<body data-product-id="{product_id}" data-price="{product_price}">
    <div class="checkout-container">
        <h1>Secure Checkout</h1>
        <div class="product-name">{product_title}</div>
        <div class="price" id="display-price">{product_price}</div>
        
        <button id="payBtn" class="btn" onclick="startPayment()">Pay Now</button>
        <div id="errorMsg" class="error"></div>
        
        <a href="index.html" class="back-link">← Back to Product</a>
    </div>

    <script>
        // Payment Server Configuration
        // 프리뷰(8090 등)에서는 로컬 payment_server(5000) 사용
        var API_BASE = "http://127.0.0.1:5000";
        try {{
            var h = window.location.hostname;
            // 로컬 환경이 아닌 경우(배포 환경)에는 상대 경로(API Routes) 사용
            if (h !== "127.0.0.1" && h !== "localhost" && window.location.protocol !== "file:") {{
                API_BASE = ""; 
            }}
        }} catch (e) {{}}
        
        var PRODUCT_ID = document.body.getAttribute('data-product-id');
        var PRICE_STR = document.body.getAttribute('data-price');
        var PRICE = parseFloat(PRICE_STR.replace(/[^0-9.]/g, '')) || 49;

        // URL 파라미터 오버라이드
        try {{
            var params = new URLSearchParams(window.location.search);
            if(params.has('price')) {{
                var p = params.get('price');
                document.getElementById('display-price').textContent = p;
                PRICE = parseFloat(p.replace(/[^0-9.]/g, '')) || PRICE;
            }}
        }} catch(e) {{}}

        async function startPayment() {{
            const btn = document.getElementById('payBtn');
            const err = document.getElementById('errorMsg');
            
            btn.disabled = true;
            btn.textContent = "Processing...";
            err.style.display = "none";

            try {{
                // Payment Server API 호출
                // API_BASE가 비어있으면(배포환경) /api/pay/start 로 호출됨 (Vercel API Route)
                var url = API_BASE + "/api/pay/start";
                // 로컬 5000번 포트일 경우 명시적 URL 사용
                if (API_BASE.includes("127.0.0.1")) {{
                     url = "http://127.0.0.1:5000/api/pay/start";
                }}

                const res = await fetch(`${{url}}?product_id=${{PRODUCT_ID}}&price_amount=${{PRICE}}&price_currency=usd`);
                const data = await res.json();
                
                if (!res.ok) {{
                    throw new Error(data.error || "Payment initialization failed");
                }}

                if (data.nowpayments && data.nowpayments.invoice_url) {{
                    window.location.href = data.nowpayments.invoice_url;
                }} else if (data.status === "paid") {{
                    btn.textContent = "Success! Redirecting...";
                    
                    // 다운로드 URL 처리
                    let downloadUrl = data.download_url;
                    if (downloadUrl && downloadUrl.startsWith("/") && API_BASE) {{
                        downloadUrl = API_BASE + downloadUrl;
                    }}
                    
                    setTimeout(() => {{
                        window.location.href = downloadUrl;
                    }}, 1000);
                }} else {{
                    throw new Error("Unexpected payment status: " + data.status);
                }}
            }} catch (e) {{
                console.error(e);
                err.textContent = e.message;
                err.style.display = "block";
                btn.disabled = false;
                btn.textContent = "Pay Now";
            }}
        }}
    </script>
</body>
</html>"""


@dataclass
class TemplateConfig:
    # 템플릿 기본 설정
    product_id: str
    brand: str
    headline: str
    subheadline: str
    product_price: str = "$49"
    primary_cta: str = "Get Started"
    secondary_cta: str = "Sign In"


class TemplateFactory:
    """
    auto_pilot이 찾아 쓸 가능성이 있는 이름(TemplateFactory)을 유지.
    실제로는 단일 파일 랜딩 생성.
    """

    def __init__(self, out_root: str = "outputs") -> None:
        # 출력 루트 폴더
        self.out_root = out_root

    def build(self, cfg: TemplateConfig) -> Dict[str, Any]:
        # product_id를 폴더명으로 안전하게 변환
        safe_pid = _safe_dirname(cfg.product_id, fallback="product")

        # 제품별 출력 폴더 결정
        out_dir = os.path.join(self.out_root, safe_pid)

        # HTML 생성
        html = _render_landing_html(
            product_id=safe_pid,
            brand=cfg.brand,
            headline=cfg.headline,
            subheadline=cfg.subheadline,
            primary_cta=cfg.primary_cta,
            secondary_cta=cfg.secondary_cta,
            product_price=cfg.product_price,
        )

        # sanitize + validate
        html = _sanitize_html(html)
        _validate_html(html)

        # 정적 배포 표준: index.html 로 저장 (Vercel에서 가장 안전)
        os.makedirs(out_dir, exist_ok=True)
        index_path = os.path.join(out_dir, "index.html")
        _write_text(index_path, html)
        
        # [NEW] checkout.html 생성
        checkout_html = _render_checkout_html(
            product_id=safe_pid,
            product_price=cfg.product_price,
            product_title=cfg.headline,
            brand=cfg.brand
        )
        checkout_path = os.path.join(out_dir, "checkout.html")
        _write_text(checkout_path, checkout_html)

        # 간단한 메타/리포트 저장
        report = {
            "product_id": safe_pid,
            "out_dir": out_dir,
            "index_html": index_path,
            "checkout_html": checkout_path,
            "sha256": _sha256_file(index_path),
            "notes": [
                "Single-file landing with embedded CSS/JS",
                "Buttons wired via data-action router",
                "Leads/auth stored in localStorage (demo)",
                "Next step: payment invoice + webhook + fulfillment",
            ],
        }
        report_path = os.path.join(out_dir, "report.json")
        _write_json(report_path, report)

        return {
            "ok": True,
            "out_dir": out_dir,
            "index_html": index_path,
            "checkout_html": checkout_path,
            "report_json": report_path,
            "sha256": report["sha256"],
        }


# -----------------------------
# 공개 API (auto_pilot 호환)
# -----------------------------


def make_template(product_id: str, **kwargs: Any) -> Dict[str, Any]:
    # make_template 진입점 (auto_pilot이 찾을 수 있게)
    return generate(product_id, **kwargs)


def make(product_id: str, **kwargs: Any) -> Dict[str, Any]:
    # make 별칭
    return generate(product_id, **kwargs)


def create(product_id: str, **kwargs: Any) -> Dict[str, Any]:
    # create 별칭
    return generate(product_id, **kwargs)


def build(product_id: str, **kwargs: Any) -> Dict[str, Any]:
    # build 별칭
    return generate(product_id, **kwargs)


def run(product_id: str, **kwargs: Any) -> Dict[str, Any]:
    # run 별칭
    return generate(product_id, **kwargs)


def generate(
    product_id: str,
    brand: str = "Web3 SaaS",
    headline: str = "Powering the Next Generation of Decentralized Applications",
    subheadline: str = "Robust tools and infrastructure for builders and businesses to deploy and scale on-chain experiences with ease.",
    product_price: str = "$49",
    primary_cta: str = "Get Started",
    secondary_cta: str = "Sign In",
    out_root: str = "outputs",
    **_: Any,
) -> Dict[str, Any]:
    """
    product_id 기준으로 outputs/<product_id>/index.html 생성.
    """
    factory = TemplateFactory(out_root=out_root)
    cfg = TemplateConfig(
        product_id=product_id,
        brand=brand,
        headline=headline,
        subheadline=subheadline,
        product_price=product_price,
        primary_cta=primary_cta,
        secondary_cta=secondary_cta,
    )
    return factory.build(cfg)


# auto_pilot 진단용: 어떤 함수들이 외부 공개인지 보여줄 수 있게
GENERATOR_PUBLIC_CALLABLES = [
    "TemplateFactory",
    "generate",
    "run",
    "build",
    "create",
    "make",
    "make_template",
]


# -----------------------------
# 로컬 단독 실행 테스트
# -----------------------------

if __name__ == "__main__":
    # 사용 예: python generator_module.py
    pid = "crypto-template-001"
    
    # 출력 폴더 생성/렌더
    result = generate(
        pid,
        brand="Web3 SaaS",
        headline="Powering the Next Generation of Decentralized Applications",
        subheadline="Our Web3 SaaS platform provides robust tools and infrastructure to build, deploy, and scale on the blockchain with ease.",
        out_root="outputs",
    )
    
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("\nOpen this file in browser (double-click):")
    print(result["index_html"])

