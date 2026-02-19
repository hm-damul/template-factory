from __future__ import annotations

import json
import os
import re
import time
import hashlib
from dataclasses import dataclass
from typing import Any, Dict

from .config import Config
from .progress_tracker import update_progress
from .schema_generator import generate_product_schema
from .schema_validator import run_rule_based_validation
from .topic_selector import select_topic
from .utils import (
    ProductionError,
    calculate_file_checksum,
    get_logger,
    handle_errors,
    retry_on_failure,
    write_json,
    write_text,
)

logger = get_logger(__name__)

# -----------------------------
# 공통 유틸 (내부 사용)
# -----------------------------


def _now_id() -> str:
    """실행 ID를 사람이 읽기 쉽게 생성합니다."""
    return time.strftime("%Y%m%d-%H%M%S")


def _safe_dirname(name: str, fallback: str = "product") -> str:
    """폴더명으로 쓰기 위험한 문자를 제거하고, 너무 길면 줄입니다(윈도우 호환)."""
    name = (name or "").strip()
    # 1. 한글 및 특수문자 제거 (영문, 숫자, 대시만 허용)
    name = re.sub(r'[^a-zA-Z0-9\s-]', '', name)
    # 2. 공백 및 특수기호를 대시로 변경
    name = re.sub(r"[\s/_:*?\"<>|]+", "-", name)
    # 3. 연속된 대시 하나로 합치기
    name = re.sub(r"-+", "-", name)
    # 4. 앞뒤 대시 및 점 제거
    name = name.strip("-. ")
    if not name:
        name = fallback
    # 5. 소문자 변환
    name = name.lower()
    if len(name) > 80:
        name = name[:80].rstrip("-")
    return name


def _sanitize_html(html: str, schema: Dict[str, Any] = None) -> str:
    """생성된 HTML에서 배포를 망치는 흔적을 제거/차단합니다."""
    html = html.replace("\x00", "")
    html = html.lstrip("\ufeff")
    html = re.sub(r"^\s*```(?:html)?\s*\n", "", html, flags=re.IGNORECASE)
    html = re.sub(r"\n\s*```\s*$", "", html)
    html = re.sub(r"\n```(?:html)?\n", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"\n```\n", "\n", html)
    # JS 내부 치환을 위해 replace 수행
    # f-string 포맷팅과 JS 중괄호 충돌 방지를 위해 별도 처리
    price = "$49"
    if schema:
        price = schema.get("_injected_price", "$49")
    final_html = html.replace("{injected_price}", price)
    
    return final_html


def _validate_html(html: str) -> None:
    """배포 실패/버튼 미동작을 유발하는 요소를 강제 검증합니다."""
    if re.search(r"(^|\n)\s*```", html):
        raise ProductionError(
            "생성된 HTML에 마크다운 코드 펜스가 포함되어 있습니다 (```).",
            stage="HTML Validation",
        )

    must_have = ["<!doctype html>", "<html", "<head", "<body", "</html>"]
    lower = html.lower()
    for token in must_have:
        if token not in lower:
            raise ProductionError(
                f"생성된 HTML에 필수 토큰이 누락되었습니다: {token}",
                stage="HTML Validation",
            )


def _build_features_html_from_schema(schema: Dict[str, Any]) -> str:
    """스키마 sections.features로 Features 섹션 HTML 생성."""
    features = (schema.get("sections") or {}).get("features") or []
    parts = []
    for f in features:
        text = (f if isinstance(f, str) else str(f)).strip() or "Feature"
        parts.append(
            f'<div class="card"><h4>{_escape_html(text)}</h4><p>{_escape_html(text)}</p></div>'
        )
    return "\n        ".join(parts) if parts else ""


def _build_pricing_html_from_schema(schema: Dict[str, Any]) -> str:
    """스키마 sections.pricing으로 Pricing 카드 1개 생성 (스키마는 단일 tier)."""
    pr = (schema.get("sections") or {}).get("pricing") or {}
    tier = (pr.get("tier_name") or "Standard").strip()
    
    # 스키마에 주입된 가격(_injected_price)이 있으면 최우선 사용
    injected_price = schema.get("_injected_price")
    if injected_price and injected_price.startswith("$"):
        price = injected_price
    else:
        price = (pr.get("price") or "").strip()
        
    if not price:
        logger.warning("Pricing missing in schema. Using '$49' default.")
        price = "$49"

    parts = [
        f'<div class="card" style="border-color: rgba(0,180,255,0.38); box-shadow: 0 24px 80px rgba(0,180,255,0.12);">'
        f'<div class="badge"><span class="pill" style="background: var(--accent2);"></span><span>{_escape_html(tier)}</span></div>'
        f'<div class="price">{_escape_html(price)}<span style="font-size:14px; color: var(--muted);">/mo</span></div>'
        f'<p class="sub" style="font-size:13px;">Best for most creators.</p>'
        f'<ul class="list"><li>Full access</li><li>Priority support</li><li>Updates included</li></ul>'
        f'<div class="row"><button class="btn btn-primary" data-action="choose-plan" data-plan="{_escape_html(tier)}" data-price="{_escape_html(price)}">{_escape_html(tier)}</button></div></div>'
    ]
    return "\n        ".join(parts)


def _build_faq_html_from_schema(schema: Dict[str, Any]) -> str:
    """스키마 sections.faq로 FAQ 섹션 HTML 생성."""
    faq = (schema.get("sections") or {}).get("faq") or []
    parts = []
    for item in faq:
        if not isinstance(item, dict):
            continue
        q = (item.get("q") or "").strip() or "Question"
        a = (item.get("a") or "").strip() or "Answer"
        parts.append(f'<div class="card"><h4>{_escape_html(q)}</h4><p>{_escape_html(a)}</p></div>')
    return "\n        ".join(parts) if parts else ""


def _pick_theme_class(title: str) -> str:
    t = (title or "").lower()
    if any(k in t for k in ("course", "cohort", "bootcamp", "academy", "curriculum", "guide", "playbook", "workshop", "masterclass")):
        return "theme-course"
    if any(k in t for k in ("dashboard", "analytics", "report", "metrics", "kpi", "tracker", "monitor")):
        return "theme-dashboard"
    if any(k in t for k in ("plugin", "plug-in", "extension", "widget", "snippet", "micro-saas", "tool", "assistant", "copilot", "automation")):
        return "theme-tool"
    if any(k in t for k in ("waitlist", "ai saas", "saas", "app", "platform", "suite", "workspace")):
        return "theme-saas"
    if any(k in t for k in ("landing", "template", "bundle", "pack")):
        return "theme-landing"
    if any(k in t for k in ("luxury", "premium", "elegant", "exclusive", "high-end", "boutique")):
        return "theme-elegant"
    if any(k in t for k in ("minimal", "clean", "simple", "pure", "essential")):
        return "theme-minimal"
    if any(k in t for k in ("play", "fun", "creative", "joy", "bright", "game")):
        return "theme-playful"
    return "theme-default"


def _render_landing_html_from_schema(schema: Dict[str, Any], brand: str = "MetaPassiveIncome") -> str:
    pid = (schema.get("product_id") or "product").strip()
    sections = schema.get("sections") or {}
    hero = sections.get("hero") or {}
    headline = (hero.get("headline") or schema.get("title") or "").strip() or "Digital Product"
    subheadline = (hero.get("subheadline") or schema.get("value_proposition") or "").strip() or ""
    cta = sections.get("cta") or {}
    primary_cta = (cta.get("text") or "Get Started").strip()
    
    design = sections.get("design") or {}
    
    features_html = _build_features_html_from_schema(schema)
    pricing_html = _build_pricing_html_from_schema(schema)
    faq_html = _build_faq_html_from_schema(schema)
    
    # 테마 클래스 결정 (스키마에 있으면 사용, 없으면 키워드 기반)
    theme_class = design.get("theme")
    if theme_class:
        theme_class = f"theme-{theme_class}"
    else:
        theme_class = _pick_theme_class(headline)
        
    # 가격 정보 추출 (JS 주입용)
    pr = (schema.get("sections") or {}).get("pricing") or {}
    injected_price = schema.get("_injected_price")
    if injected_price and injected_price.startswith("$"):
        product_price = injected_price
    else:
        product_price = (pr.get("price") or "").strip()
    if not product_price:
        product_price = "$49"

    return _render_landing_html(
        product_id=pid,
        brand=brand,
        headline=headline,
        subheadline=subheadline,
        primary_cta=primary_cta,
        secondary_cta="Sign In",
        features_html=features_html or None,
        pricing_html=pricing_html or None,
        faq_html=faq_html or None,
        theme_class=theme_class,
        design_meta=design,
        product_price=product_price
    )


def _render_main_content_markdown(schema: Dict[str, Any]) -> str:
    """스키마에서 메인 콘텐츠 파일(product.md)용 마크다운 생성."""
    title = (schema.get("title") or "").strip() or "Product"
    value_prop = (schema.get("value_proposition") or "").strip()
    sections = schema.get("sections") or {}
    problem = (sections.get("problem") or {}).get("description") or ""
    solution = (sections.get("solution") or {}).get("description") or ""
    features = sections.get("features") or []
    benefits = sections.get("benefits") or []
    lines = [f"# {title}", "", value_prop, "", "## Problem", "", problem, "", "## Solution", "", solution]
    if features:
        lines.extend(["", "## Features", ""] + [f"- {f}" for f in features if isinstance(f, str)])
    if benefits:
        lines.extend(["", "## Benefits", ""] + [f"- {b}" for b in benefits if isinstance(b, str)])
    faq = sections.get("faq") or []
    if faq:
        lines.extend(["", "## FAQ", ""])
        for item in faq:
            if isinstance(item, dict):
                lines.append(f"**{item.get('q', '')}**")
                lines.append(f"{item.get('a', '')}")
                lines.append("")
    return "\n".join(lines).strip() + "\n"


# -----------------------------
# 랜딩 HTML 생성 (내장 CSS/JS)
# -----------------------------


def _escape_html(s: str) -> str:
    """HTML 속성/내용 삽입용 이스케이프."""
    if not s:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _render_landing_html(
    product_id: str,
    brand: str,
    headline: str,
    subheadline: str,
    primary_cta: str,
    secondary_cta: str,
    features_html: str | None = None,
    pricing_html: str | None = None,
    faq_html: str | None = None,
    theme_class: str = "theme-default",
    design_meta: Dict[str, Any] | None = None,
    product_price: str = "$59",
) -> str:
    """단일 HTML 파일에 모든 기능(내장 CSS/JS)을 포함하여 렌더링합니다. 스키마에서 생성한 HTML을 넘기면 해당 블록을 사용합니다."""
    design = design_meta or {}
    layout_style = design.get("layout_style", "minimalist")
    primary_color = design.get("primary_color", "#00b4ff")
    secondary_color = design.get("secondary_color", "#22d3ee")
    font_family = design.get("font_family", "Inter, system-ui, sans-serif")

    layout = "default"
    if theme_class == "theme-course":
        layout = "course"
    elif theme_class == "theme-dashboard":
        layout = "dashboard"
    elif theme_class == "theme-tool":
        layout = "tool"
    elif theme_class in ("theme-saas", "theme-landing", "theme-modern", "theme-dark", "theme-tech"):
        layout = "saas"
    elif theme_class == "theme-elegant":
        layout = "elegant"
    elif theme_class == "theme-minimal":
        layout = "minimal"

    nav_features_label = "Features"
    nav_pricing_label = "Pricing"
    nav_faq_label = "FAQ"
    features_title = "Features"
    pricing_title = "Pricing"
    faq_title = "FAQ"
    kicker_text = "Web3-ready SaaS landing • Professional Template"

    if layout == "course":
        nav_features_label = "Curriculum"
        nav_pricing_label = "Enroll"
        features_title = "What you'll build"
        pricing_title = "Course access"
        kicker_text = "Cohort-style course landing optimized for high-ticket programs"
    elif layout == "dashboard":
        nav_features_label = "Dashboards"
        nav_pricing_label = "Plans"
        features_title = "Dashboards and views"
        pricing_title = "Workspace plans"
        kicker_text = "Analytics/dashboard template focused on KPIs and live metrics"
    elif layout == "tool":
        nav_features_label = "How it works"
        nav_pricing_label = "Pricing"
        features_title = "How the tool works"
        pricing_title = "License"
        kicker_text = "Plugin/tool landing tuned for marketplace-style sales"
    elif layout == "elegant":
        kicker_text = "Premium high-end design for exclusive digital assets"
    elif layout == "minimal":
        kicker_text = "Distraction-free landing focused on pure value proposition"

    # 기본 features/faq/pricing (스키마 미제공 시)
    if features_html is None:
        features_html = """
        <div class="card"><h4>Wallet-ready checkout</h4><p>Designed for crypto-wallet users. Next step: invoice creation + webhook → fulfillment.</p></div>
        <div class="card"><h4>One-file deploy</h4><p>No build step required. Works on Vercel static hosting. No missing JS bundles.</p></div>
        <div class="card"><h4>Action router</h4><p>All buttons use <code>data-action</code>. Easy to extend with payment + download gating.</p></div>
        """
    if pricing_html is None:
        pricing_html = """
        <div class="pricing-card">
            <div class="badge"><span class="pill"></span><span>Starter</span></div>
            <div class="price">$19<span>/mo</span></div>
            <p style="font-size:13px; color:var(--muted); margin-bottom:16px;">For early users testing your checkout.</p>
            <ul class="features">
                <li>Basic analytics</li>
                <li>Email lead capture</li>
                <li>Community support</li>
            </ul>
            <button class="btn btn-primary" data-action="choose-plan" data-plan="Starter" data-price="$19">Buy Starter</button>
        </div>
        <div class="pricing-card" style="border-color: var(--accent2); box-shadow: 0 10px 30px rgba(0,180,255,0.1);">
            <div class="badge"><span class="pill" style="background: var(--accent2);"></span><span>Pro</span></div>
            <div class="price">{product_price}<span>/mo</span></div>
            <p style="font-size:13px; color:var(--muted); margin-bottom:16px;">For sales-focused crypto products.</p>
            <ul class="features">
                <li>Plan gating ready</li>
                <li>Webhook endpoint scaffold</li>
                <li>Priority support</li>
            </ul>
            <button class="btn btn-primary" data-action="choose-plan" data-plan="Pro" data-price="{product_price}">Buy Pro</button>
        </div>
        <div class="pricing-card">
            <div class="badge"><span class="pill" style="background: #ffb703;"></span><span>Enterprise</span></div>
            <div class="price">$199<span>/mo</span></div>
            <p style="font-size:13px; color:var(--muted); margin-bottom:16px;">For teams requiring custom flows.</p>
            <ul class="features">
                <li>Custom domains</li>
                <li>Dedicated onboarding</li>
                <li>SLA support</li>
            </ul>
            <button class="btn btn-primary" data-action="choose-plan" data-plan="Enterprise" data-price="$199">Buy Enterprise</button>
        </div>
        """
    if faq_html is None:
        faq_html = """
        <div class="card"><h4>Why are buttons sometimes unresponsive?</h4><p>If the HTML file is wrapped in markdown fences or served escaped, the DOM differs and scripts may not run as expected.</p></div>
        <div class="card"><h4>Where does payment integration go?</h4><p>Next module: serverless function (Vercel) → create invoice → receive webhook → unlock download/email.</p></div>
        """
    # Hero image logic (Enhanced for diversity and relevance)
    keywords = headline.lower().split()
    
    # Calculate numeric price for Schema.org
    price_numeric = product_price.replace("$", "").replace(",", "").strip()
    if not price_numeric:
        price_numeric = "49.00"
    
    # Category-based image pools for diversity
    image_pools = {
        "crypto": [
            "https://images.unsplash.com/photo-1621761191319-c6fb62004009?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1639710339852-514d33dded47?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1518546305927-5a555bb7020d?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1633356122544-f134324a6cee?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1622633054716-a218f224741e?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1634733988138-bf2c3a2a13fa?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1605792657660-596af9039a27?q=80&w=2000&auto=format&fit=crop"
        ],
        "course": [
            "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1524178232363-1fb2b075b655?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1501504905252-473c47e087f8?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1434030216411-0b793f4b4173?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1522202176988-66273c2fd55f?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1523240715181-2f0f9f225839?q=80&w=2000&auto=format&fit=crop"
        ],
        "dashboard": [
            "https://images.unsplash.com/photo-1551288049-bebda4e38f71?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1460925895917-afdab827c52f?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1543286386-713bdd548da4?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1581291417004-6e7398463c68?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1551434678-e076c223a692?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1504868584819-f8eec2421750?q=80&w=2000&auto=format&fit=crop"
        ],
        "saas": [
            "https://images.unsplash.com/photo-1519389950473-47ba0277781c?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1551434678-e076c223a692?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1498050108023-c5249f4df085?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1522071820081-009f0129c71c?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1460925895917-afdab827c52f?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1531403009284-440f080d1e12?q=80&w=2000&auto=format&fit=crop"
        ],
        "marketing": [
            "https://images.unsplash.com/photo-1557804506-669a67965ba0?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1460925895917-afdab827c52f?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1533750349088-cd871a92f312?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1556761175-5973dc0f32e7?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1552664730-d307ca884978?q=80&w=2000&auto=format&fit=crop"
        ],
        "ai": [
            "https://images.unsplash.com/photo-1677442136019-21780ecad995?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1675271591211-126ad94c495d?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1593349480506-8433a14cc64e?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1672911739264-2f306ca8a221?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1664575602276-acd073f104c1?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1617839623591-c5a50a5e4c41?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1507146426996-ef05306b995a?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1531746790731-6c087fecd05a?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?q=80&w=2000&auto=format&fit=crop"
        ],
        "default": [
            "https://images.unsplash.com/photo-1639762681485-074b7f938ba0?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1633356122544-f134324a6cee?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1550745165-9bc0b252726f?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1518770660439-4636190af475?q=80&w=2000&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?q=80&w=2000&auto=format&fit=crop"
        ]
    }

    # Deterministic selection based on product_id hash
    seed = int(hashlib.md5(product_id.encode()).hexdigest(), 16)
    
    category = "default"
    headline_lower = headline.lower()
    
    if any(k in headline_lower for k in ["ai", "artificial intelligence", "machine learning", "automation", "gpt"]):
        category = "ai"
    elif any(k in headline_lower for k in ["crypto", "bitcoin", "ethereum", "wallet", "web3", "blockchain", "defi"]):
        category = "crypto"
    elif any(k in headline_lower for k in ["course", "learn", "education", "training", "guide", "tutorial", "masterclass"]):
        category = "course"
    elif any(k in headline_lower for k in ["dashboard", "analytics", "data", "stats", "insights", "metrics"]):
        category = "dashboard"
    elif any(k in headline_lower for k in ["tool", "software", "saas", "app", "platform", "automation"]):
        category = "saas"
    elif any(k in headline_lower for k in ["marketing", "business", "consulting", "strategy", "sales", "revenue"]):
        category = "marketing"

    pool = image_pools.get(category, image_pools["default"])
    hero_image_url = pool[seed % len(pool)]


    # HTML 템플릿 (기존 generator_module.py의 내용을 그대로 사용)
    html = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <meta name=\"description\" content=\"{subheadline}\" />
  <meta name=\"keywords\" content=\"{headline.replace(' ', ', ')}, digital product, passive income, {brand}\" />
  <meta property=\"og:title\" content=\"{brand} | {headline}\" />
  <meta property=\"og:description\" content=\"{subheadline}\" />
  <meta property=\"og:image\" content=\"{hero_image_url}\" />
  <meta property=\"og:type\" content=\"website\" />
  <meta property=\"og:site_name\" content=\"{brand}\" />
  <meta name=\"twitter:card\" content=\"summary_large_image\" />
  <meta name=\"twitter:title\" content=\"{brand} | {headline}\" />
  <meta name=\"twitter:description\" content=\"{subheadline}\" />
  <meta name=\"twitter:image\" content=\"{hero_image_url}\" />
  <meta name=\"robots\" content=\"index, follow\" />
  <link rel=\"canonical\" href=\"https://meta-passive-income-{product_id}.vercel.app\" />
  
  <script type=\"application/ld+json\">
  {{
    \"@context\": \"https://schema.org/\",
    \"@type\": \"Product\",
    \"name\": \"{headline}\",
    \"description\": \"{subheadline}\",
    \"brand\": {{
      \"@type\": \"Brand\",
      \"name\": \"{brand}\"
    }},
    \"offers\": {{
      \"@type\": \"Offer\",
      \"priceCurrency\": \"USD\",
      \"price\": \"{price_numeric}\",
      \"availability\": \"https://schema.org/InStock\"
    }}
  }}
  </script>
  <link rel=\"icon\" href=\"data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><rect width=%22100%22 height=%22100%22 fill=%22%2300b4ff%22></rect></svg>\">
  <title>{brand} | {headline}</title>

  <style>
    :root {{
      --bg: #070b12;
      --panel: rgba(255,255,255,0.06);
      --panel2: rgba(255,255,255,0.08);
      --text: rgba(255,255,255,0.92);
      --muted: rgba(255,255,255,0.68);
      --line: rgba(255,255,255,0.12);
      --glow: {primary_color}55;
      --accent: {primary_color};
      --accent2: {secondary_color};
      --danger: #ff4d6d;
      --ok: #2ee59d;
      --radius: 16px;
      --font-main: {font_family};
    }}

    /* Urgency & Social Proof Styles */
    .urgency-bar {{
      background: var(--danger);
      color: white;
      text-align: center;
      padding: 8px;
      font-size: 13px;
      font-weight: 700;
      position: sticky;
      top: 0;
      z-index: 100;
    }}

    .notification-popup {{
      position: fixed;
      bottom: 20px;
      left: 20px;
      background: var(--panel);
      border: 1px solid var(--line);
      padding: 12px 18px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      gap: 12px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.2);
      z-index: 1000;
      transform: translateY(150%);
      transition: transform 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }}

    .notification-popup.show {{
      transform: translateY(0);
    }}

    body.theme-course {{
      --bg: #0b0814;
      --accent: {primary_color};
      --accent2: {secondary_color};
      --glow: {primary_color}33;
    }}

    body.theme-elegant {{
      --bg: #0f172a;
      --accent: {primary_color};
      --accent2: {secondary_color};
      --glow: {primary_color}25;
      --radius: 4px;
    }}

    body.theme-minimal {{
      --bg: #ffffff;
      --text: #1e293b;
      --muted: #64748b;
      --line: #e2e8f0;
      --panel: #f8fafc;
      --panel2: #f1f5f9;
      --accent: {primary_color};
      --accent2: {secondary_color};
      --glow: {primary_color}1a;
    }}

    body.theme-playful {{
      --bg: #fdf2f8;
      --text: #831843;
      --muted: #be185d;
      --line: #fbcfe8;
      --panel: #ffffff;
      --panel2: #fce7f3;
      --accent: {primary_color};
      --accent2: {secondary_color};
      --glow: {primary_color}20;
      --radius: 24px;
    }}

    body.theme-dashboard {{
      --bg: #020617;
      --accent: {primary_color};
      --accent2: {secondary_color};
      --glow: {primary_color}32;
    }}

    body.theme-landing {{
      --bg: #020617;
      --accent: {primary_color};
      --accent2: {secondary_color};
      --glow: {primary_color}32;
    }}

    body.theme-saas {{
      --bg: #020617;
      --accent: {primary_color};
      --accent2: {secondary_color};
      --glow: {primary_color}32;
    }}

    body.theme-tool {{
      --bg: #020617;
      --accent: {primary_color};
      --accent2: {secondary_color};
      --glow: {primary_color}34;
    }}

    * {{
      box-sizing: border-box;
    }}

    html, body {{
      margin: 0;
      padding: 0;
      background: radial-gradient(1200px 800px at 70% 20%, {primary_color}1a, transparent 55%),
                  radial-gradient(900px 600px at 25% 30%, {secondary_color}14, transparent 55%),
                  var(--bg);
      color: var(--text);
      font-family: var(--font-main);
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

    /* Layout Styles */
    .layout-grid .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 24px;
    }}

    .layout-creative .hero {{
      text-align: left;
      display: flex;
      align-items: center;
      gap: 40px;
    }}

    .layout-creative .hero-content {{
      flex: 1;
    }}

    .layout-corporate .container {{
      max-width: 900px;
    }}

    .layout-minimalist .hero {{
      padding: 120px 24px;
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

    .hero-preview {{
      position: relative;
    }}

    .hero-image {{
      width: 100%;
      border-radius: 18px;
      border: 1px solid var(--line);
      box-shadow: 0 32px 64px rgba(0,0,0,0.4);
      background: rgba(255,255,255,0.02);
      aspect-ratio: 16 / 10;
      object-fit: cover;
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

    .pricing-card {{
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 16px;
      padding: 24px;
      display: flex;
      flex-direction: column;
      transition: transform 0.2s ease, border-color 0.2s ease;
    }}

    .pricing-card:hover {{
      transform: translateY(-4px);
      border-color: var(--accent);
      background: rgba(255,255,255,0.05);
    }}

    .pricing-card h3 {{
      margin: 0;
      font-size: 18px;
    }}

    .pricing-card .price {{
      font-size: 36px;
      font-weight: 800;
      margin: 16px 0;
      color: var(--text);
    }}

    .pricing-card .price span {{
      font-size: 14px;
      color: var(--muted);
      font-weight: 400;
    }}

    .pricing-card .features {{
      list-style: none;
      padding: 0;
      margin: 0 0 24px 0;
      flex-grow: 1;
    }}

    .pricing-card .features li {{
      padding: 8px 0;
      color: var(--muted);
      font-size: 14px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .pricing-card .features li::before {{
      content: "✓";
      color: var(--accent);
      font-weight: bold;
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

<body data-product-id=\"{product_id}\" class=\"{theme_class} layout-{layout_style}\">
  <div class=\"urgency-bar\">
    LIMITED TIME OFFER: Save 50% for the next <span id=\"countdown\">15:00</span>
  </div>
  <div class=\"nav\">
    <div class=\"nav-inner\">
      <div class=\"brand\">
        <div class=\"logo\" aria-hidden=\"true\"></div>
        <div>{brand}</div>
      </div>

      <div class=\"nav-links\" aria-label=\"Primary\">
        <a href=\"#features\" data-action=\"nav\" data-target=\"#features\">{nav_features_label}</a>
        <a href=\"#pricing\" data-action=\"nav\" data-target=\"#pricing\">{nav_pricing_label}</a>
        <a href=\"#faq\" data-action=\"nav\" data-target=\"#faq\">{nav_faq_label}</a>
      </div>

      <div class=\"nav-actions\">
        <button class=\"btn\" data-action=\"open-login\">{secondary_cta}</button>
        <button class=\"btn btn-primary\" data-action=\"open-plans\">{primary_cta}</button>
      </div>
    </div>
  </div>

  <main class=\"container\">
    <div class=\"hero\">
      <div class=\"hero-grid\">
        <div>
          <div class=\"kicker\">
            <span class=\"kicker-dot\"></span>
            <span>{kicker_text}</span>
          </div>
          <h1>{headline}</h1>
          <p class=\"sub\">{subheadline}</p>

          <div class=\"hero-actions\">
            <button class=\"btn btn-primary\" data-action=\"open-plans\" style=\"padding: 14px 24px; font-size: 16px;\">{primary_cta}</button>
            <button class=\"btn\" data-action=\"scroll\" data-target=\"#features\" style=\"padding: 14px 24px; font-size: 16px;\">Learn More</button>
          </div>
        </div>
        <div class=\"hero-preview\">
          <img src=\"{hero_image_url}\" alt=\"Product Preview\" class=\"hero-image\" loading=\"lazy\" />
        </div>
      </div>
    </div>

    <section id=\"features\">
      <h2 class=\"section-title\">{features_title}</h2>
      <div class=\"grid3\">
        {features_html}
      </div>
    </section>

    <section id=\"pricing\">
      <h2 class=\"section-title\">{pricing_title}</h2>
      <div class=\"pricing\">
        {pricing_html}
      </div>
    </section>

    <section id=\"faq\">
      <h2 class=\"section-title\">{faq_title}</h2>
      <div class=\"faq\">
        {faq_html}
      </div>
    </section>

    <footer>
      <div style=\"margin-top:6px;\">© {brand}. All rights reserved.</div>
    </footer>
  </main>

  <div class=\"notification-popup\" id=\"purchase-notification\">
    <div style=\"font-size: 20px;\">🔥</div>
    <div>
      <div style=\"font-weight: 700; font-size: 14px;\" id=\"notif-name\">Someone from USA</div>
      <div style=\"font-size: 12px; color: var(--muted);\">just purchased this product</div>
    </div>
  </div>

  <!-- Login Modal -->
  <div class=\"modal-backdrop\" id=\"modal-login\" role=\"dialog\" aria-modal=\"true\" aria-label=\"Login modal\">
    <div class=\"modal\">
      <div class=\"modal-head\">
        <h3 class=\"modal-title\">Sign In</h3>
        <button class=\"x\" data-action=\"close-modal\" data-target=\"#modal-login\">X</button>
      </div>

      <div class=\"field\">
        <label class=\"label\">Email</label>
        <input class=\"input\" id=\"login-email\" placeholder=\"you@example.com\" />
      </div>

      <div class=\"field\">
        <label class=\"label\">Password</label>
        <input class=\"input\" id=\"login-pass\" type=\"password\" placeholder=\"••••••••\" />
      </div>

      <div class=\"row\">
        <button class=\"btn btn-primary\" data-action=\"do-login\">Sign In</button>
        <button class=\"btn\" data-action=\"close-modal\" data-target=\"#modal-login\">Cancel</button>
      </div>
    </div>
  </div>

  <!-- Plans Modal -->
  <div class=\"modal-backdrop\" id=\"modal-plans\" role=\"dialog\" aria-modal=\"true\" aria-label=\"Plans modal\">
    <div class=\"modal\">
      <div class=\"modal-head\">
        <h3 class=\"modal-title\">Get Started</h3>
        <button class=\"x\" data-action=\"close-modal\" data-target=\"#modal-plans\">X</button>
      </div>

      <p style=\"margin: 0; color: var(--muted); font-size: 13px;\">
        Choose a plan, enter your email, and we'll \"capture a lead\". Payment step will replace this later.
      </p>

      <div class=\"field\">
        <label class=\"label\">Email</label>
        <input class=\"input\" id=\"lead-email\" placeholder=\"lead@example.com\" />
      </div>

      <div class=\"field\">
        <label class=\"label\">Selected Plan</label>
        <input class=\"input\" id=\"lead-plan\" placeholder=\"(select below)\" readonly />
      </div>

      <div class="row" id="plan-buttons">
        <!-- Dynamic buttons injected by JS -->
      </div>

      <div class=\"row\">
        <button class=\"btn btn-primary\" data-action=\"submit-lead\">Continue</button>
        <button class=\"btn\" data-action=\"check-payment\">I already paid</button>
        <button class=\"btn\" data-action=\"close-modal\" data-target=\"#modal-plans\">Close</button>
      </div>
    </div>
  </div>

  <!-- Toast -->
  <div class=\"toast\" id=\"toast\"></div>

  <script>
    (function() {{
      "use strict";

      // 404 Error Suppressor for Vite/Client, Favicon, and Source Maps in previews
      (function() {{
        var originalError = console.error;
        var originalWarn = console.warn;
        
        console.error = function() {{
          var msg = arguments[0];
          if (msg && typeof msg === 'string') {{
            if (msg.indexOf('/@vite/client') !== -1 || 
                msg.indexOf('Failed to load resource') !== -1 ||
                msg.indexOf('favicon.ico') !== -1 ||
                msg.indexOf('.map') !== -1) {{
              return;
            }}
          }}
          originalError.apply(console, arguments);
        }};

        console.warn = function() {{
          var msg = arguments[0];
          if (msg && typeof msg === 'string') {{
            if (msg.indexOf('SourceMap') !== -1 || msg.indexOf('.map') !== -1) {{
              return;
            }}
          }}
          originalWarn.apply(console, arguments);
        }};
      }})();

      // ----- 작은 유틸 -----
      function qs(sel) {{ return document.querySelector(sel); }}
      function qsa(sel) {{ return Array.from(document.querySelectorAll(sel)); }}

      function isLocalPreview() {{
        try {{
          var h = window.location.hostname || "";
          var p = String(window.location.port || "");
          var prot = window.location.protocol || "";
          // 8090(preview)은 전체 페이지 미리보기를 위해 리다이렉트 제외
          // 8099(dashboard) 환경에서만 체크아웃 리다이렉트 허용
          if (p === "8099" || h === "127.0.0.1" || h === "localhost" || prot === "file:") {{
              if (p === "8090") return false;
              return true;
          }}
          return false;
        }} catch (e) {{
          return false;
        }}
      }}

      // 프리뷰(8090 등)에서는 로컬 payment_server(5000) 사용
      var API_BASE = "http://127.0.0.1:5000";
      try {{
        var h = window.location.hostname;
        // 로컬 환경이 아닌 경우(배포 환경)에는 상대 경로 사용
        if (h !== "127.0.0.1" && h !== "localhost" && window.location.protocol !== "file:") {{
           API_BASE = ""; 
        }}
      }} catch (e) {{}}

      // 가격 동적 생성 (하드코딩 제거)
      try {{
        var planBtns = document.getElementById("plan-buttons");
        if (planBtns) {{
            // 스키마에서 주입된 가격 정보 사용 (localStorage 무시)
            planBtns.innerHTML = `
                <button class="btn btn-primary" data-action="choose-plan" data-plan="Standard" data-price="{product_price}">
                    Standard License ({product_price})
                </button>
            `;
        }}
      }} catch(e) {{}}

      function showToast(msg) {{
        var t = qs(\"#toast\");
        if (!t) return;
        t.textContent = msg;
        t.style.display = \"block\";
        clearTimeout(window.__toastTimer);
        window.__toastTimer = setTimeout(function() {{
          t.style.display = \"none\";
        }}, 2200);
      }}

      function openModal(id) {{
        var el = qs(id);
        if (!el) return;
        el.style.display = \"flex\";
      }}

      function closeModal(id) {{
        var el = qs(id);
        if (!el) return;
        el.style.display = \"none\";
      }}

      function scrollToTarget(hash) {{
        try {{
          var el = qs(hash);
          if (el) {{
            el.scrollIntoView({{ behavior: \"smooth\", block: \"start\" }});
          }}
        }} catch (e) {{}}
      }}

      // ----- Marketing Urgency & Social Proof -----
      function startCountdown(durationSec) {{
        var timer = durationSec, minutes, seconds;
        var el = qs(\"#countdown\");
        if (!el) return;
        setInterval(function () {{
          minutes = parseInt(timer / 60, 10);
          seconds = parseInt(timer % 60, 10);
          minutes = minutes < 10 ? \"0\" + minutes : minutes;
          seconds = seconds < 10 ? \"0\" + seconds : seconds;
          el.textContent = minutes + \":\" + seconds;
          if (--timer < 0) timer = durationSec;
        }}, 1000);
      }}

      function startSocialProof() {{
        var names = [\"Alex\", \"Sarah\", \"Michael\", \"Elena\", \"Ji-hoon\", \"Chloe\", \"David\", \"Yuki\"];
        var locations = [\"USA\", \"UK\", \"Germany\", \"South Korea\", \"Japan\", \"Canada\", \"Singapore\"];
        var notif = qs(\"#purchase-notification\");
        var nameEl = qs(\"#notif-name\");
        if (!notif || !nameEl) return;

        function showNotif() {{
          var name = names[Math.floor(Math.random() * names.length)];
          var loc = locations[Math.floor(Math.random() * locations.length)];
          nameEl.textContent = name + \" from \" + loc;
          notif.classList.add(\"show\");
          setTimeout(function() {{
            notif.classList.remove(\"show\");
          }}, 5000);
        }}

        setInterval(showNotif, 20000 + Math.random() * 20000);
        setTimeout(showNotif, 3000);
      }}

      // Init Marketing
      startCountdown(15 * 60);
      startSocialProof();

      // ----- 로컬 저장 (데모) -----
      var productId = document.body.getAttribute(\"data-product-id\") || \"product\";
      var KEY_LEADS = productId + \":leads\";
      var KEY_PLAN  = productId + \":plan\";
      var KEY_PRICE = productId + \":price\";
      var KEY_ORDER = productId + \":order\";
      var KEY_AUTH  = productId + \":auth\";

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

      // ----- 로직 유틸 -----
      async function startPay(plan) {{
        var rawPrice = localStorage.getItem(KEY_PRICE) || \"$19\";
        // rawPrice가 null/undefined일 경우를 대비한 안전한 문자열 변환 (NoneType 에러 방지)
        var safePriceStr = String(rawPrice || \"$19\");
        var numericPrice = parseFloat(safePriceStr.replace(/[^0-9.]/g, \"\")) || 19;

        showToast(\"Starting checkout for \" + plan + \" (\" + rawPrice + \")...\");
        
        // 1) 로컬 프리뷰 환경에서 대시보드 체크아웃 페이지(MetaMask 등)가 우선인지 확인
        if (isLocalPreview()) {{
           var checkoutUrl = \"http://127.0.0.1:8099/checkout/\" + productId;
           // 대시보드 서버가 살아있는지 확인은 생략하고 바로 리다이렉트 시도 (사용자 경험 우선)
           showToast(\"Redirecting to secure checkout...\");
           setTimeout(function() {{
             window.location.href = checkoutUrl;
           }}, 800);
           return;
        }}

        try {{
          // GET request to avoid 405 error (fallback supported on server)
          var params = \"product_id=\" + encodeURIComponent(productId) + 
                       \"&price_amount=\" + encodeURIComponent(numericPrice) + 
                       \"&price_currency=usd\";
          var res = await fetch(API_BASE + \"/api/pay/start?\" + params, {{
            method: \"GET\",
            headers: {{ \"Content-Type\": \"application/json\" }}
          }});

          var data = await res.json().catch(function() {{ return {{}}; }});
          if (!res.ok) {{
            if (data.can_request) {{
              alert(data.message || \"Product needs regeneration. Please leave a comment on the WordPress post!\");
            }} else {{
              showToast(\"Payment failed: \" + (data.error || res.status));
            }}
            return;
          }}

          if (data.order_id) {{
            localStorage.setItem(KEY_ORDER, String(data.order_id));
          }}

          // 2) 실제 결제창(NowPayments) 전환
          if (data.nowpayments && data.nowpayments.invoice_url) {{
            showToast(\"Redirecting to payment gateway...\");
            setTimeout(function() {{
              window.location.href = data.nowpayments.invoice_url;
            }}, 1000);
          }} 
          // 3) Mock 모드인 경우에도 즉시 다운로드 대신 '결제 진행 중' 느낌을 주기 위해 모달이나 지연 처리
          else if (data.status === \"paid\") {{
            showToast(\"Success! Processing your order...\");
            setTimeout(function() {{
              var url = data.download_url;
              if (API_BASE && url && url.indexOf(\"http\") !== 0 && url[0] === \"/\") {{
                url = API_BASE + url;
              }}
              // 로컬 미리보기(8090/8099) 환경이고 URL이 /api/pay/download로 시작하면 dashboard의 프록시를 통하도록 유도
               if (false && isLocalPreview() && url && url.indexOf("/api/pay/download") !== -1) {{
                 var currentPort = window.location.port;
                 if (currentPort === \"8090\" || currentPort === \"8099\") {{
                   url = (url || \"\").replace(\"127.0.0.1:5000\", window.location.host);
                 }}
               }}
               window.location.href = url || (\"/downloads/\" + productId + \"/package.zip\");
            }}, 2000); // 2초 정도 '지연'을 주어 결제된 느낌을 줌
          }} else {{
            showToast(\"Order created: \" + (data.order_id || \"pending\"));
          }}
        }} catch (e) {{
          showToast(\"Error: \" + (e.message || String(e)));
        }}
      }}

      async function checkPay() {{
        var orderId = localStorage.getItem(KEY_ORDER) || "";
        if (!orderId) {{
          showToast("No recent payment to check. Start checkout first.");
          return;
        }}
        showToast("Checking payment status...");
        try {{
          var url = API_BASE + "/api/pay/check?order_id=" + encodeURIComponent(orderId) + "&product_id=" + encodeURIComponent(productId);
          var res = await fetch(url, {{ method: "GET" }});
          var data = await res.json().catch(function() {{ return {{}}; }});
          if (!res.ok) {{
            showToast("Check failed: " + (data.error || res.status));
            return;
          }}
          if (data.status === "paid" && data.download_url) {{
            showToast("Payment confirmed. Redirecting to download...");
            setTimeout(function() {{
              var url = data.download_url;
              if (API_BASE && url && url.indexOf("http") !== 0 && url[0] === "/") {{
                url = API_BASE + url;
              }}
              // 로컬 미리보기(8090/8099) 환경이고 URL이 /api/pay/download로 시작하면 dashboard의 프록시를 통하도록 유도
              if (isLocalPreview() && url && url.indexOf("/api/pay/download") !== -1) {{
                // dashboard_server.py(8099)가 프록시 라우트를 가지고 있으므로 호스트를 변경
                var currentPort = window.location.port;
                if (currentPort === "8099") {{
                  url = (url || "").replace("127.0.0.1:5000", window.location.host);
                }}
              }}
              window.location.href = url;
            }}, 800);
          }} else {{
            showToast("Payment not confirmed yet. Status: " + (data.status || "pending"));
          }}
        }} catch (e) {{
          showToast("Error: " + (e.message || String(e)));
        }}
      }}

      // ----- 액션 라우터 -----
      var actions = {{
        \"nav\": function(el) {{
          var target = el.getAttribute(\"data-target\") || el.getAttribute(\"href\") || \"#features\";
          if (target.startsWith(\"#\")) {{
            scrollToTarget(target);
          }}
        }},

        \"scroll\": function(el) {{
          var target = el.getAttribute(\"data-target\") || \"#features\";
          if (target.startsWith(\"#\")) {{
            scrollToTarget(target);
          }}
        }},

        \"open-login\": function() {{
          openModal(\"#modal-login\");
          setTimeout(function() {{
            var inp = qs(\"#login-email\");
            if (inp) inp.focus();
          }}, 50);
        }},

        \"open-plans\": function() {{
          openModal(\"#modal-plans\");
          // 모달 오픈 시 현재 선택된 플랜 표시
          var plan = localStorage.getItem(KEY_PLAN) || \"\";
          var leadPlan = qs(\"#lead-plan\");
          if (leadPlan) leadPlan.value = plan;
          setTimeout(function() {{
            var inp = qs(\"#lead-email\");
            if (inp) inp.focus();
          }}, 50);
        }},

        \"close-modal\": function(el) {{
          var target = el.getAttribute(\"data-target\");
          if (target) closeModal(target);
        }},

        \"choose-plan\": function(el) {{
          var plan = el.getAttribute(\"data-plan\") || \"Starter\";
          var price = el.getAttribute(\"data-price\") || \"$19\";
          localStorage.setItem(KEY_PLAN, plan);
          localStorage.setItem(KEY_PRICE, price);

          var leadPlan = qs(\"#lead-plan\");
          if (leadPlan) leadPlan.value = plan;
          showToast(\"Plan selected: \" + plan + \" (\" + price + \")\");
          openModal(\"#modal-plans\");
        }},

        \"submit-lead\": function() {{
          var emailEl = qs(\"#lead-email\");
          var plan = localStorage.getItem(KEY_PLAN) || \"\";
          var email = (emailEl ? emailEl.value : \"\").trim();

          if (!plan) {{
            showToast(\"Select a plan first.\");
            return;
          }}
          if (!email || email.indexOf(\"@\") < 0) {{
            showToast(\"Enter a valid email.\");
            return;
          }}

          var leads = readJson(KEY_LEADS, []);
          leads.push({{
            email: email,
            plan: plan,
            at: new Date().toISOString()
          }});
          writeJson(KEY_LEADS, leads);

          showToast(\"Lead captured. Proceeding to payment...\");

          setTimeout(function() {{
            closeModal(\"#modal-plans\");
            startPay(plan);
          }}, 800);
        }},

        \"check-payment\": function() {{
          checkPay();
        }},

        \"do-login\": function() {{
          var emailEl = qs(\"#login-email\");
          var passEl = qs(\"#login-pass\");
          var email = (emailEl ? emailEl.value : \"\").trim();
          var pass = (passEl ? passEl.value : \"\").trim();

          if (!email || email.indexOf(\"@\") < 0) {{
            showToast(\"Enter a valid email.\");
            return;
          }}
          if (!pass) {{
            showToast(\"Enter a password.\");
            return;
          }}

          localStorage.setItem(KEY_AUTH, email);
          showToast(\"Signed in: \" + email);
          closeModal(\"#modal-login\");
        }},

        \"reset-demo\": function() {{
          localStorage.removeItem(KEY_LEADS);
          localStorage.removeItem(KEY_PLAN);
          localStorage.removeItem(KEY_AUTH);
          var leadPlan = qs(\"#lead-plan\");
          var leadEmail = qs(\"#lead-email\");
          if (leadPlan) leadPlan.value = \"\";
          if (leadEmail) leadEmail.value = \"\";
          showToast(\"Reset.\");
        }}
      }};

      function handleClick(e) {{
        var el = e.target;
        // 버튼 안쪽 span 클릭 등 대비: data-action 가진 조상까지 탐색
        while (el && el !== document.body) {{
          var act = el.getAttribute && el.getAttribute(\"data-action\");
          if (act) {{
            e.preventDefault();
            var fn = actions[act];
            if (fn) {{
              fn(el);
            }} else {{
              showToast(\"Unknown action: \" + act);
            }}
            return;
          }}
          el = el.parentNode;
        }}
      }}

      // ----- 해시 라우팅(단순) -----
      function onHashChange() {{
        var h = location.hash || \"\";
        if (h && h.startsWith(\"#\")) {{
          // 모달 해시 같은 건 쓰지 않고 섹션만 처리
          if (qs(h)) {{
            scrollToTarget(h);
          }}
        }}
      }}

      // ----- 초기 바인딩 -----
      document.addEventListener(\"click\", handleClick);
      window.addEventListener(\"hashchange\", onHashChange);

      // ESC로 모달 닫기
      document.addEventListener(\"keydown\", function(e) {{
        if (e.key === \"Escape\") {{
          closeModal(\"#modal-login\");
          closeModal(\"#modal-plans\");
        }}
      }});

      // 백드롭 클릭 시 닫기
      qsa(\".modal-backdrop\").forEach(function(bd) {{
        bd.addEventListener(\"click\", function(e) {{
          if (e.target === bd) {{
            bd.style.display = \"none\";
          }}
        }});
      }});

      // 초기 해시 처리
      onHashChange();

      // showToast(\"JS loaded.\");
    }})();
  </script>
</body>
</html>
"""
    return html


# -----------------------------
# 제품 생성 팩토리
# -----------------------------


@dataclass
class ProductGenerationConfig:
    """제품 생성에 필요한 설정 데이터 클래스. topic은 스키마 생성 시 사용(선택)."""

    product_id: str
    brand: str
    headline: str
    subheadline: str
    primary_cta: str = "Get Started"
    secondary_cta: str = "Sign In"
    topic: str = ""
    price_usd: float | None = None
    price_comparison: str | None = None


class ProductGenerator:
    """디지털 제품 자산(예: 랜딩 페이지 HTML)을 생성하는 클래스"""

    def __init__(self, output_root_dir: str = Config.OUTPUT_DIR) -> None:
        """생성기 초기화. 출력 루트 디렉토리를 설정합니다."""
        self.output_root_dir = output_root_dir
        logger.info(
            f"ProductGenerator 초기화 완료. 출력 디렉토리: {self.output_root_dir}"
        )

    @handle_errors(stage="Generate")
    @retry_on_failure(max_retries=3)
    def generate_product_assets(
        self, config: ProductGenerationConfig
    ) -> Dict[str, Any]:
        """스키마 기반으로 제품 자산을 생성합니다. AI 스키마 생성 → 규칙 검증 → HTML/MD 렌더 → 저장."""
        safe_pid = _safe_dirname(config.product_id, fallback="product")
        product_output_dir = os.path.join(self.output_root_dir, safe_pid)
        os.makedirs(product_output_dir, exist_ok=True)

        logger.info(
            f"제품 자산 생성 시작 - ID: {config.product_id}, 출력 경로: {product_output_dir}"
        )
        update_progress("Product Creation", "Starting generation", 10, f"ID: {safe_pid}", safe_pid)

        # 1. 스키마 기반 AI 생성 (유효하지 않으면 재시도 후 fallback)
        if not (config.topic or "").strip() or (config.topic or "").strip().lower() in {"auto", "default"}:
            sel = select_topic(config.headline or "")
            config.topic = sel.get("topic") or (config.headline or safe_pid)
            config.headline = sel.get("headline") or (config.headline or config.topic)
            config.subheadline = sel.get("subheadline") or config.subheadline
        topic = (config.topic or config.headline or safe_pid).strip()

        # [AI Web Integration] Research Topic Trends
        research_context = None
        try:
            update_progress("Product Creation", "Researching topic", 15, f"Topic: {topic}", safe_pid)
            from .ai_web_researcher import web_researcher
            logger.info(f"AI Web Researching topic: {topic}")
            research_context = web_researcher.research_topic_trends(topic)
        except Exception as e:
            logger.warning(f"Web research failed, proceeding without context: {e}")

        update_progress("Product Creation", "Generating schema", 25, "AI generating content structure...", safe_pid)
        schema = generate_product_schema(
            topic=topic,
            product_id=safe_pid,
            headline=config.headline,
            subheadline=config.subheadline,
            brand=config.brand,
            price_usd=config.price_usd,
            price_comparison=config.price_comparison,
            context=research_context,
        )

        # 2. 결정론적 규칙 검증 (실패 시 생성 단계 실패로 처리)
        update_progress("Product Creation", "Validating schema", 35, "Checking structure rules...", safe_pid)
        rule_result = run_rule_based_validation(schema)
        if not rule_result.passed:
            logger.warning("스키마 규칙 검증 실패: %s", rule_result.errors)
            raise ProductionError(
                f"스키마 규칙 검증 실패: {rule_result.errors}",
                stage="Generate",
                product_id=config.product_id,
            )

        # 3. product_schema.json 저장 (QA Stage 1에서 스키마/규칙/AI 품질 검사에 사용)
        # 중요: 프리미엄 엔진에서 결정된 최종 가격(final_price_usd)을 스키마에 동기화
        final_price_str = "$49"
        
        if config.price_usd:
            final_price_str = f"${config.price_usd:.2f}"
            schema.setdefault("sections", {}).setdefault("pricing", {})["price"] = final_price_str
        else:
            # Config에 없으면 스키마의 기존 가격 존중
            pr = (schema.get("sections") or {}).get("pricing") or {}
            existing_price = pr.get("price")
            if existing_price and str(existing_price).startswith("$"):
                final_price_str = existing_price
            
        schema_path = os.path.join(product_output_dir, "product_schema.json")
        write_json(schema_path, schema)

        # 4. 스키마에서 랜딩 HTML 및 메인 콘텐츠 렌더
        # HTML 렌더링 시 가격 정보를 주입하기 위해 스키마에 명시적으로 추가
        update_progress("Product Creation", "Rendering HTML", 45, "Generating landing page...", safe_pid)
        schema["_injected_price"] = final_price_str
        
        html_content = _render_landing_html_from_schema(schema, brand=config.brand)
        html_content = _sanitize_html(html_content, schema)
        _validate_html(html_content)

        index_html_path = os.path.join(product_output_dir, "index.html")
        write_text(index_html_path, html_content)

        main_content_file = (schema.get("assets") or {}).get("main_content_file") or "product.md"
        main_content_path = os.path.join(product_output_dir, main_content_file)
        write_text(main_content_path, _render_main_content_markdown(schema))

        file_checksum = calculate_file_checksum(index_html_path)

        generation_report = {
            "product_id": safe_pid,
            "output_dir": product_output_dir,
            "main_asset": index_html_path,
            "schema_path": schema_path,
            "main_content_path": main_content_path,
            "checksum": file_checksum,
            "generated_at": _now_id(),
            "status": "GENERATED_SUCCESS",
            "schema_driven": True,
            "notes": [
                "스키마 기반 생성 (product_schema.json)",
                "단일 파일 랜딩 페이지 (CSS/JS 내장)",
                "데이터 액션 라우터를 통한 버튼 기능",
            ],
        }
        report_json_path = os.path.join(product_output_dir, "generation_report.json")
        write_json(report_json_path, generation_report)

        logger.info(f"제품 자산 생성 완료 - ID: {config.product_id}")
        update_progress("Product Creation", "Assets generated", 50, "Ready for next stage", safe_pid)
        return {
            "ok": True,
            "product_id": safe_pid,
            "output_dir": product_output_dir,
            "main_asset_path": index_html_path,
            "schema_path": schema_path,
            "checksum": file_checksum,
            "report_path": report_json_path,
        }


# -----------------------------
# 공개 API (auto_pilot 호환성을 위해 유지)
# -----------------------------


def generate(
    product_id: str,
    brand: str = "Web3 SaaS",
    headline: str = "Powering the Next Generation of Decentralized Applications",
    subheadline: str = "Robust tools and infrastructure for builders and businesses to deploy and scale on-chain experiences with ease.",
    primary_cta: str = "Get Started",
    secondary_cta: str = "Sign In",
    output_root_dir: str = Config.OUTPUT_DIR,
    **_: Any,
) -> Dict[str, Any]:
#     """
#     제품 ID를 기반으로 outputs/<product_id>/index.html 및 관련 자산을 생성합니다.
#     이 함수는 ProductGenerator 클래스의 래퍼 역할을 합니다.
#     """
    generator = ProductGenerator(output_root_dir=output_root_dir)
    cfg = ProductGenerationConfig(
        product_id=product_id,
        brand=brand,
        headline=headline,
        subheadline=subheadline,
        primary_cta=primary_cta,
        secondary_cta=secondary_cta,
    )
    return generator.generate_product_assets(cfg)


# auto_pilot 진단용: 어떤 함수들이 외부 공개인지 보여줄 수 있게
GENERATOR_PUBLIC_CALLABLES = [
    "ProductGenerator",  # 클래스 노출
    "generate",
    # 이전 auto_pilot 호환을 위해 필요하다면 여기에 별칭 함수들을 추가할 수 있습니다.
    # 예: "run", "build", "create", "make", "make_template"
]

# -----------------------------
# 로컬 단독 실행 테스트
# -----------------------------

if __name__ == "__main__":
    # 테스트를 위한 .env 파일 설정 (예시)
    # .env 파일에 다음 내용을 추가하세요:
    # LEMON_SQUEEZY_API_KEY="your_lemon_squeezy_api_key"
    # GITHUB_TOKEN="your_github_token"
    # VERCEL_API_TOKEN="your_vercel_api_token"
    # JWT_SECRET_KEY="your_jwt_secret_key"
    # DOWNLOAD_TOKEN_EXPIRY_SECONDS=3600
    # DATABASE_URL="sqlite:///./product_factory.db"

    # Config.validate()가 main 실행 시 호출되므로, .env 파일이 없으면 에러 발생 가능
    # 테스트를 위해 임시로 환경 변수 설정 (실제 배포 시 .env 사용)
    # os.environ["LEMON_SQUEEZY_API_KEY"] = "dummy_key"
    # os.environ["GITHUB_TOKEN"] = "dummy_token"
    # os.environ["VERCEL_API_TOKEN"] = "dummy_vercel_token"
    # os.environ["JWT_SECRET_KEY"] = "supersecretjwtkey"

    # Config 클래스 재로드 (환경 변수 변경 후)
    # from importlib import reload
    # reload(Config)

    logger.info("ProductGenerator 모듈 로컬 테스트 시작")

    test_product_id = "test-crypto-landing-page-001"

    try:
        # ProductGenerator 인스턴스 생성
        generator = ProductGenerator()

        # 제품 생성 설정
        test_config = ProductGenerationConfig(
            product_id=test_product_id,
            brand="CryptoNexus",
            headline="Unlock the Future of Decentralized Finance",
            subheadline="Seamlessly manage your crypto assets and explore new opportunities with our secure platform.",
            primary_cta="Start Building",
            secondary_cta="Log In",
        )

        # 제품 자산 생성 실행
        result = generator.generate_product_assets(test_config)

        logger.info("제품 생성 결과:")
        logger.info(json.dumps(result, ensure_ascii=False, indent=2))
        logger.info(
            f"\n브라우저에서 파일 열기 (더블 클릭): {result['main_asset_path']}"
        )

    except ProductionError as pe:
        logger.error(f"생산 오류 발생: {pe.message}")
        if pe.original_exception:
            logger.error(f"원본 예외: {pe.original_exception}")
    except Exception as e:
        logger.error(f"예기치 않은 오류 발생: {e}")

    logger.info("ProductGenerator 모듈 로컬 테스트 완료")
