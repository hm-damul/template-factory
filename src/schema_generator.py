# -*- coding: utf-8 -*-
"""
schema_generator.py

스키마 기반 AI 생성: 토픽을 입력받아 PRODUCT SCHEMA에 맞는 JSON을 생성합니다.
유효하지 않은 JSON 또는 스키마 불일치 시 수정 프롬프트로 자동 재시도.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

import requests

from .product_schema import (
    get_product_schema_definition,
    parse_product_schema_json,
)
from .schema_validator import run_rule_based_validation
from .utils import get_logger, ProductionError
from .niche_data import NICHE_CONTENT_MAP, get_niche_for_topic

logger = get_logger(__name__)

# 재시도 횟수 (invalid JSON / schema mismatch 시)
MAX_SCHEMA_RETRIES = 3

AI_API_KEY = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
AI_API_BASE = os.getenv("AI_API_BASE", "https://api.deepseek.com/v1")
AI_MODEL = os.getenv("AI_QUALITY_MODEL", "deepseek-chat")

# Gemini API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

try:
    import google.genai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False


def _call_gemini(system: str, user: str, max_tokens: int = 4000) -> str | None:
    """Google Gemini API 호출 (New SDK)."""
    if not GEMINI_API_KEY or not HAS_GEMINI:
        return None
    
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=f"{system}\n\nUser Request:\n{user}",
            config=genai.types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=0.3,
            )
        )
        return response.text
    except Exception as e:
        logger.error(f"Gemini API 호출 실패: {e}")
        return None


def _call_llm(system: str, user: str, max_tokens: int = 4000) -> str | None:
    """OpenAI 호환 Chat Completions 호출, 실패 시 Gemini 시도."""
    
    # 1. Try DeepSeek/OpenAI if configured
    if AI_API_KEY:
        url = f"{AI_API_BASE.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": AI_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=90)
            resp.raise_for_status()
            content = (resp.json().get("choices") or [{}])[0].get("message", {}).get("content")
            if content:
                return content
        except Exception as e:
            logger.warning(f"DeepSeek/OpenAI API 호출 실패 ({e}). Gemini로 전환 시도.")

    # 2. Try Gemini fallback
    if GEMINI_API_KEY and HAS_GEMINI:
        logger.info("DeepSeek/OpenAI 실패 또는 미설정. Gemini API를 사용합니다.")
        return _call_gemini(system, user, max_tokens)
        
    return None


def _build_fallback_schema(
    product_id: str,
    topic: str,
    headline: str,
    subheadline: str,
    brand: str = "MetaPassiveIncome",
    price_usd: float | None = None,
) -> Dict[str, Any]:
    """
    AI 미사용 시 결정론적 스키마 생성. 규칙 검증을 통과하도록 최소 필드를 채웁니다.
    """
    safe_id = (product_id or "product").strip() or "product"
    title = headline or f"Digital Product: {topic}"
    # 결정론적 디자인 선택 (product_id 기반)
    import hashlib
    seed_val = int(hashlib.sha256(safe_id.encode()).hexdigest()[:8], 16)
    themes = ["saas", "landing", "modern", "dark", "tech", "minimal", "elegant"]
    layouts = ["minimalist", "bold", "professional", "creative"]
    colors = ["#00b4ff", "#6366f1", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"]
    fonts = ["Inter, sans-serif", "Roboto, sans-serif", "system-ui, sans-serif", "Georgia, serif"]
    
    selected_theme = themes[seed_val % len(themes)]
    selected_layout = layouts[seed_val % len(layouts)]
    selected_color = colors[seed_val % len(colors)]
    selected_font = fonts[seed_val % len(fonts)]
    
    # Niche data for fallback
    niche_key = get_niche_for_topic(topic)
    niche_data = NICHE_CONTENT_MAP.get(niche_key, NICHE_CONTENT_MAP["default"])
    niche_templates = niche_data.get("schema_templates", NICHE_CONTENT_MAP["default"]["schema_templates"])

    if price_usd is None:
        import random
        # Fallback to a random price if none provided, to ensure diversity
        price_usd = random.choice([29, 39, 49, 59, 79])

    return {
        "product_id": safe_id,
        "title": title,
        "target_customer": f"Creators and merchants interested in {topic}",
        "value_proposition": subheadline or f"Launch wallet-ready sales with {topic}: checkout, token-gated delivery, and lead capture.",
        "sections": {
            "hero": {
                "headline": headline or title,
                "subheadline": subheadline or f"Deploy a one-file landing with wallet checkout and token-gated downloads for {topic}.",
            },
            "problem": {
                "description": niche_templates["problem"].replace("{topic}", topic),
            },
            "solution": {
                "description": niche_templates["solution"].replace("{topic}", topic),
            },
            "features": [f"{f} for {topic}" if "{topic}" not in f else f.replace("{topic}", topic) for f in niche_templates["features"]],
            "benefits": [
                f"Ship faster with ready {topic} templates",
                f"Increase conversion with clear {topic} value prop",
                f"Operate with predictable {topic} delivery flow",
                f"Scale experimentation with simple {topic} A/B hooks"
            ],
            "pricing": {
                "tier_name": "Standard Access",
                "price": f"${price_usd or 49}",
            },
            "faq": [
                {"q": "What is included?", "a": f"You get the full landing page, the {topic} guide, and automated delivery setup."},
                {"q": "How do I deploy?", "a": "Upload to Vercel, Netlify, or any static host. No backend needed."},
                {"q": "Is it secure?", "a": "Yes, it uses wallet-based authentication for delivery gating."},
            ],
            "cta": {"text": "Get Started Now"},
            "design": {
                "theme": selected_theme,
                "primary_color": selected_color,
                "secondary_color": selected_color,
                "font_family": selected_font,
                "layout_style": selected_layout
            }
        },
        "assets": {
            "main_content_file": "product.pdf",
            "landing_page": "index.html",
        },
    }


def generate_product_schema(
    topic: str,
    product_id: str,
    headline: str = "",
    subheadline: str = "",
    brand: str = "MetaPassiveIncome",
    price_usd: float | None = None,
    price_comparison: str | None = None,
    context: str | None = None,
) -> Dict[str, Any]:
    """
    토픽과 설정으로 PRODUCT SCHEMA에 맞는 JSON을 생성합니다.
    AI 실패 또는 API 미설정 시 결정론적 fallback 스키마를 반환합니다.
    """
    schema_def = get_product_schema_definition()
    schema_def_str = json.dumps(schema_def, ensure_ascii=False, indent=2)

    price_rule = f"- sections.pricing.price: set to exactly ${price_usd:.2f}" if price_usd else "- sections.pricing.tier_name and price: choose a single, one-time commercial license price that is competitive with top 10% selling templates (typically in the $59–$149 range). Prefer higher but still realistic pricing (e.g. \"Pro\" and \"$89\")."
    comparison_rule = f"- Pricing context/analysis: {price_comparison}" if price_comparison else ""
    context_rule = f"\n- Web Research Context: {context}\n- Use this context to make the copy data-driven, competitive, and SEO-optimized." if context else ""

    system = f"""You are a product copywriter and pricing strategist for top-selling digital templates (ThemeForest, Creative Market, Gumroad, etc.). Generate a digital product schema as valid JSON only (no markdown fences, no explanation).
Strict schema to follow (all fields required, exact structure):
{schema_def_str}

Rules:
- product_id: use exactly: {product_id}
- title, target_customer, value_proposition: clear and specific for the topic
- sections.hero.headline / subheadline: compelling and topic-specific; use language similar to high-converting template marketplaces
- sections.problem.description: one paragraph
- sections.solution.description: one paragraph
- sections.features: array of at least 3 feature strings focused on conversion and ease of launch
- sections.benefits: array of at least 3 benefit strings focused on revenue, speed-to-market, and differentiation
{price_rule}
{comparison_rule}
{context_rule}
- sections.faq: array of at least 3 objects with "q" and "a" that reduce purchase friction (update, license, customization, payment, refund, etc.)
- sections.cta.text: short CTA text focused on buying or downloading now
- Copywriting Strategy:
    - Use the PAS (Problem-Agitation-Solution) framework for the Problem and Solution sections to create deep emotional resonance.
    - Use the AIDA (Attention-Interest-Desire-Action) flow across the Hero and Features sections.
    - Tone: Expert, authoritative, yet highly accessible and results-oriented.
- sections.design: choose a visual identity that matches the topic:
    - theme: one of [modern, dark, elegant, playful, tech, minimal]
    - primary_color / secondary_color: HEX codes that look premium and match the theme
    - font_family: a professional Google Font or system stack (e.g. "Inter, sans-serif", "Playfair Display, serif")
    - layout_style: one of [minimalist, grid, corporate, creative]
- assume buyers primarily in high-revenue markets (US, UK, Canada, Germany, Australia, Singapore, South Korea). Write copy in natural US English targeted at these audiences.
- assets.main_content_file: "product.md"
- assets.landing_page: "index.html"

Output only the JSON object, no other text."""

    user = f"Topic: {topic}\n\nGenerate the complete product schema JSON for this topic. Use current best practices from high-converting template marketplaces and set pricing on the higher but realistic end of the market. Output only valid JSON."

    for attempt in range(MAX_SCHEMA_RETRIES):
        raw = _call_llm(system, user)
        if not raw:
            break
        try:
            data = parse_product_schema_json(raw)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("스키마 JSON 파싱 실패 (시도 %s): %s", attempt + 1, e)
            user = f"Previous response was invalid JSON. Error: {e}\n\nGenerate again. Output ONLY valid JSON, no markdown."
            continue

        # product_id 강제 일치
        data["product_id"] = (product_id or data.get("product_id") or "product").strip() or "product"
        data.setdefault("assets", {})["main_content_file"] = "product.md"
        data.setdefault("assets", {})["landing_page"] = "index.html"

        result = run_rule_based_validation(data)
        if result.passed:
            logger.info("스키마 생성 성공 (시도 %s)", attempt + 1)
            return data
        logger.warning("스키마 규칙 검증 실패 (시도 %s): %s", attempt + 1, result.errors)
        user = f"Schema validation failed: {result.errors}\n\nFix these and output only valid JSON again."

    # Fallback
    logger.warning("AI 스키마 생성 실패. 결정론적 fallback 스키마를 사용합니다.")
    return _build_fallback_schema(
        product_id=product_id,
        topic=topic,
        headline=headline,
        subheadline=subheadline,
        brand=brand,
        price_usd=price_usd,
    )

