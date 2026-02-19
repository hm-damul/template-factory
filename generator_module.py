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

    /* 모달 */
    .modal-backdrop {{
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.62);
      display: none;
      align-items: center;
      justify-content: center;
      padding: 18px;
      z-index: 200;
    }}

    .modal {{
      width: min(560px, 100%);
      background: rgba(10,14,22,0.92);
      border: 1px solid rgba(255,255,255,0.14);
      border-radius: 18px;
      box-shadow: 0 30px 90px rgba(0,0,0,0.55);
      padding: 16px;
    }}

    .modal-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
    }}

    .modal-title {{
      margin: 0;
      font-size: 16px;
      letter-spacing: -0.2px;
    }}

    .x {{
      border: 1px solid rgba(255,255,255,0.14);
      background: rgba(255,255,255,0.06);
      color: var(--text);
      border-radius: 12px;
      padding: 8px 10px;
      cursor: pointer;
      font-weight: 800;
    }}

    .field {{
      margin-top: 10px;
    }}

    .label {{
      display: block;
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 6px;
    }}

    .input {{
      width: 100%;
      padding: 12px 12px;
      border-radius: 12px;
      border: 1px solid rgba(255,255,255,0.14);
      background: rgba(255,255,255,0.05);
      color: var(--text);
      outline: none;
    }}

    .hint {{
      margin-top: 8px;
      font-size: 12px;
      color: rgba(255,255,255,0.62);
    }}

    .row {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 12px;
    }}

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

  <!-- Login Modal -->
  <div class="modal-backdrop" id="modal-login" role="dialog" aria-modal="true" aria-label="Login modal">
    <div class="modal">
      <div class="modal-head">
        <h3 class="modal-title">Sign In</h3>
        <button class="x" data-action="close-modal" data-target="#modal-login">X</button>
      </div>

      <div class="field">
        <label class="label">Email</label>
        <input class="input" id="login-email" placeholder="you@example.com" />
      </div>

      <div class="field">
        <label class="label">Password</label>
        <input class="input" id="login-pass" type="password" placeholder="••••••••" />
      </div>

      <div class="row">
        <button class="btn btn-primary" data-action="do-login">Sign In</button>
        <button class="btn" data-action="close-modal" data-target="#modal-login">Cancel</button>
      </div>
    </div>
  </div>

  <!-- Plans Modal -->
  <div class="modal-backdrop" id="modal-plans" role="dialog" aria-modal="true" aria-label="Plans modal">
    <div class="modal">
      <div class="modal-head">
        <h3 class="modal-title">Get Started</h3>
        <button class="x" data-action="close-modal" data-target="#modal-plans">X</button>
      </div>

      <p style="margin: 0; color: var(--muted); font-size: 13px;">
        Choose a plan, enter your email, and we'll "capture a lead". Payment step will replace this later.
      </p>

      <div class="field">
        <label class="label">Email</label>
        <input class="input" id="lead-email" placeholder="lead@example.com" />
      </div>

      <div class="field">
        <label class="label">Selected Plan</label>
        <input class="input" id="lead-plan" placeholder="(select below)" readonly />
      </div>

      <div class="row">
        <button class="btn" data-action="choose-plan" data-plan="Starter">Starter</button>
        <button class="btn" data-action="choose-plan" data-plan="Pro">Pro</button>
        <button class="btn" data-action="choose-plan" data-plan="Enterprise">Enterprise</button>
      </div>

      <div class="row">
        <button class="btn btn-primary" data-action="submit-lead">Continue</button>
        <button class="btn" data-action="close-modal" data-target="#modal-plans">Close</button>
      </div>

      <div class="hint">Captured leads: localStorage["{product_id}:leads"]</div>
    </div>
  </div>

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

      function openModal(id) {{
        var el = qs(id);
        if (!el) return;
        el.style.display = "flex";
      }}

      function closeModal(id) {{
        var el = qs(id);
        if (!el) return;
        el.style.display = "none";
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

      // refreshStats removed

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
          openModal("#modal-login");
          setTimeout(function() {{
            var inp = qs("#login-email");
            if (inp) inp.focus();
          }}, 50);
        }},

        "open-plans": function() {{
          openModal("#modal-plans");
          // 모달 오픈 시 현재 선택된 플랜 표시
          var plan = localStorage.getItem(KEY_PLAN) || "";
          var leadPlan = qs("#lead-plan");
          if (leadPlan) leadPlan.value = plan;
          setTimeout(function() {{
            var inp = qs("#lead-email");
            if (inp) inp.focus();
          }}, 50);
        }},

        "close-modal": function(el) {{
          var target = el.getAttribute("data-target");
          if (target) closeModal(target);
        }},

        "choose-plan": function(el) {{
          var plan = el.getAttribute("data-plan") || "Starter";
          localStorage.setItem(KEY_PLAN, plan);
          var leadPlan = qs("#lead-plan");
          if (leadPlan) leadPlan.value = plan;
          showToast("Plan selected: " + plan);
          // refreshStats();
        }},

        "submit-lead": function() {{
          var emailEl = qs("#lead-email");
          var plan = localStorage.getItem(KEY_PLAN) || "";
          var email = (emailEl ? emailEl.value : "").trim();

          if (!plan) {{
            showToast("Select a plan first.");
            return;
          }}
          if (!email || email.indexOf("@") < 0) {{
            showToast("Enter a valid email.");
            return;
          }}

          var leads = readJson(KEY_LEADS, []);
          leads.push({{
            email: email,
            plan: plan,
            at: new Date().toISOString()
          }});
          writeJson(KEY_LEADS, leads);

          showToast("Lead captured.");
          // refreshStats();

          // 다음 단계(결제)로 갈 훅 포인트:
          // 여기서 서버에 invoice 생성 요청 → 결제 URL로 리다이렉트 로직을 붙이면 됨.
          closeModal("#modal-plans");
        }},

        "do-login": function() {{
          var emailEl = qs("#login-email");
          var passEl = qs("#login-pass");
          var email = (emailEl ? emailEl.value : "").trim();
          var pass = (passEl ? passEl.value : "").trim();

          if (!email || email.indexOf("@") < 0) {{
            showToast("Enter a valid email.");
            return;
          }}
          if (!pass) {{
            showToast("Enter a password.");
            return;
          }}

          localStorage.setItem(KEY_AUTH, email);
          showToast("Signed in: " + email);
          // refreshStats();
          closeModal("#modal-login");
        }},

        "reset-demo": function() {{
          localStorage.removeItem(KEY_LEADS);
          localStorage.removeItem(KEY_PLAN);
          localStorage.removeItem(KEY_AUTH);
          var leadPlan = qs("#lead-plan");
          var leadEmail = qs("#lead-email");
          if (leadPlan) leadPlan.value = "";
          if (leadEmail) leadEmail.value = "";
          showToast("Reset.");
          // refreshStats();
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
          // 모달 해시 같은 건 쓰지 않고 섹션만 처리
          if (qs(h)) {{
            scrollToTarget(h);
          }}
        }}
      }}

      // ----- 초기 바인딩 -----
      document.addEventListener("click", handleClick);
      window.addEventListener("hashchange", onHashChange);

      // ESC로 모달 닫기
      document.addEventListener("keydown", function(e) {{
        if (e.key === "Escape") {{
          closeModal("#modal-login");
          closeModal("#modal-plans");
        }}
      }});

      // 백드롭 클릭 시 닫기
      qsa(".modal-backdrop").forEach(function(bd) {{
        bd.addEventListener("click", function(e) {{
          if (e.target === bd) {{
            bd.style.display = "none";
          }}
        }});
      }});

      // 상태 갱신
      // refreshStats();

      // 초기 해시 처리
      onHashChange();

      // showToast("JS loaded.");
    }})();
  </script>
</body>
</html>
# """
#     return html
# 
# 
# -----------------------------
# 설정/팩토리
# -----------------------------
# 
# 
# @dataclass
# class TemplateConfig:
    # 템플릿 기본 설정
#     product_id: str
#     brand: str
#     headline: str
#     subheadline: str
#     primary_cta: str = "Get Started"
#     secondary_cta: str = "Sign In"
# 
# 
# class TemplateFactory:
#     """
#     auto_pilot이 찾아 쓸 가능성이 있는 이름(TemplateFactory)을 유지.
#     실제로는 단일 파일 랜딩 생성.
#     """
# 
#     def __init__(self, out_root: str = "outputs") -> None:
#         # 출력 루트 폴더
#         self.out_root = out_root
# 
#     def build(self, cfg: TemplateConfig) -> Dict[str, Any]:
#         # product_id를 폴더명으로 안전하게 변환
#         safe_pid = _safe_dirname(cfg.product_id, fallback="product")
# 
#         # 제품별 출력 폴더 결정
#         out_dir = os.path.join(self.out_root, safe_pid)
# 
#         # HTML 생성
#         html = _render_landing_html(
#             product_id=safe_pid,
#             brand=cfg.brand,
#             headline=cfg.headline,
#             subheadline=cfg.subheadline,
#             primary_cta=cfg.primary_cta,
#             secondary_cta=cfg.secondary_cta,
#         )
# 
#         # sanitize + validate
#         html = _sanitize_html(html)
#         _validate_html(html)
# 
#         # 정적 배포 표준: index.html 로 저장 (Vercel에서 가장 안전)
#         os.makedirs(out_dir, exist_ok=True)
#         index_path = os.path.join(out_dir, "index.html")
#         _write_text(index_path, html)
# 
#         # 간단한 메타/리포트 저장
#         report = {
#             "product_id": safe_pid,
#             "out_dir": out_dir,
#             "index_html": index_path,
#             "sha256": _sha256_file(index_path),
#             "notes": [
#                 "Single-file landing with embedded CSS/JS",
#                 "Buttons wired via data-action router",
#                 "Leads/auth stored in localStorage (demo)",
#                 "Next step: payment invoice + webhook + fulfillment",
#             ],
#         }
#         report_path = os.path.join(out_dir, "report.json")
#         _write_json(report_path, report)
# 
#         return {
#             "ok": True,
#             "out_dir": out_dir,
#             "index_html": index_path,
#             "report_json": report_path,
#             "sha256": report["sha256"],
#         }


# -----------------------------
# 공개 API (auto_pilot 호환)
# -----------------------------


# def make_template(product_id: str, **kwargs: Any) -> Dict[str, Any]:
#     # make_template 진입점 (auto_pilot이 찾을 수 있게)
#     return generate(product_id, **kwargs)


# def make(product_id: str, **kwargs: Any) -> Dict[str, Any]:
#     # make 별칭
#     return generate(product_id, **kwargs)


# def create(product_id: str, **kwargs: Any) -> Dict[str, Any]:
#     # create 별칭
#     return generate(product_id, **kwargs)


# def build(product_id: str, **kwargs: Any) -> Dict[str, Any]:
#     # build 별칭
#     return generate(product_id, **kwargs)


# def run(product_id: str, **kwargs: Any) -> Dict[str, Any]:
#     # run 별칭
#     return generate(product_id, **kwargs)
# 
# 
# def generate(
#     product_id: str,
#     brand: str = "Web3 SaaS",
#     headline: str = "Powering the Next Generation of Decentralized Applications",
#     subheadline: str = "Robust tools and infrastructure for builders and businesses to deploy and scale on-chain experiences with ease.",
#     primary_cta: str = "Get Started",
#     secondary_cta: str = "Sign In",
#     out_root: str = "outputs",
#     **_: Any,
# ) -> Dict[str, Any]:
#     """
#     product_id 기준으로 outputs/<product_id>/index.html 생성.
#     """
#     factory = TemplateFactory(out_root=out_root)
#     cfg = TemplateConfig(
#         product_id=product_id,
#         brand=brand,
#         headline=headline,
#         subheadline=subheadline,
#         primary_cta=primary_cta,
#         secondary_cta=secondary_cta,
#     )
#     return factory.build(cfg)


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
    # pid = "crypto-template-001"
    #
    # # 출력 폴더 생성/렌더
    # result = generate(
    #     pid,
    #     brand="Web3 SaaS",
    #     headline="Powering the Next Generation of Decentralized Applications",
    #     subheadline="Our Web3 SaaS platform provides robust tools and infrastructure to build, deploy, and scale on the blockchain with ease.",
    #     out_root="outputs",
    # )
    #
    # print(json.dumps(result, ensure_ascii=False, indent=2))
    # print("\nOpen this file in browser (double-click):")
    # print(result["index_html"])
    pass
