# -*- coding: utf-8 -*-
"""
product_schema.py

스키마 기반 AI 제품 공장: 모든 생성 제품이 따라야 하는 엄격한 PRODUCT SCHEMA 정의.
이 스키마에 맞는 JSON만 QA Stage 1의 스키마 검증을 통과할 수 있다.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

# -----------------------------
# 스키마 구조 (요구사항과 동일)
# -----------------------------

# 스키마 버전 (호환성 추적)
SCHEMA_VERSION = 1

# 필수 최소 개수 (규칙 기반 검증용)
MIN_FEATURES = 3
MIN_BENEFITS = 3
MIN_FAQ = 3

# 콘텐츠 품질 임계값 (AI 비율 강화용)
MIN_TITLE_LENGTH = 10
MIN_DESCRIPTION_LENGTH = 50
MIN_VALUE_PROP_LENGTH = 30
MIN_BENEFIT_LENGTH = 15
MIN_FAQ_A_LENGTH = 20


def get_product_schema_definition() -> Dict[str, Any]:
    """
    모든 생성 제품이 준수해야 하는 PRODUCT SCHEMA 정의를 반환합니다.
    AI 생성 프롬프트 및 검증기에 사용됩니다.
    """
    return {
        "product_id": "string",
        "title": "string",
        "target_customer": "string",
        "value_proposition": "string",
        "sections": {
            "hero": {"headline": "string", "subheadline": "string"},
            "problem": {"description": "string"},
            "solution": {"description": "string"},
            "features": ["string"],
            "benefits": ["string"],
            "pricing": {"tier_name": "string", "price": "string"},
            "faq": [{"q": "string", "a": "string"}],
            "cta": {"text": "string"},
            "design": {
                "theme": "string",
                "primary_color": "string",
                "secondary_color": "string",
                "font_family": "string",
                "layout_style": "string"
            }
        },
        "assets": {
            "main_content_file": "string",
            "landing_page": "string",
        },
    }


def get_empty_schema_template() -> Dict[str, Any]:
    """빈 값으로 채워진 스키마 템플릿. 필드 존재 여부 검증용."""
    return {
        "product_id": "",
        "title": "",
        "target_customer": "",
        "value_proposition": "",
        "sections": {
            "hero": {"headline": "", "subheadline": ""},
            "problem": {"description": ""},
            "solution": {"description": ""},
            "features": [],
            "benefits": [],
            "pricing": {"tier_name": "", "price": ""},
            "faq": [],
            "cta": {"text": ""},
            "design": {
                "theme": "",
                "primary_color": "",
                "secondary_color": "",
                "font_family": "",
                "layout_style": ""
            }
        },
        "assets": {
            "main_content_file": "",
            "landing_page": "",
        },
    }


def required_paths() -> List[List[str]]:
    """
    스키마 내 필수 경로 목록 (리스트 인덱스 제외, 존재 여부만 검사).
    규칙: 모든 필드 존재, features/benefits/faq는 개수만 별도 검사.
    """
    return [
        ["product_id"],
        ["title"],
        ["target_customer"],
        ["value_proposition"],
        ["sections", "hero", "headline"],
        ["sections", "hero", "subheadline"],
        ["sections", "problem", "description"],
        ["sections", "solution", "description"],
        ["sections", "features"],
        ["sections", "benefits"],
        ["sections", "pricing", "tier_name"],
        ["sections", "pricing", "price"],
        ["sections", "faq"],
        ["sections", "cta", "text"],
        ["assets", "main_content_file"],
        ["assets", "landing_page"],
    ]


def get_nested(data: Dict[str, Any], path: List[str]) -> Any:
    """path로 중첩 딕셔너리 값을 조회. 없으면 None."""
    cur = data
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def schema_to_flat_string(d: Dict[str, Any]) -> str:
    """스키마를 읽기 쉬운 한 줄 요약 문자열로 변환 (로깅/디버깅용)."""
    try:
        title = d.get("title") or d.get("product_id") or "?"
        n_f = len(d.get("sections", {}).get("features") or [])
        n_b = len(d.get("sections", {}).get("benefits") or [])
        n_faq = len(d.get("sections", {}).get("faq") or [])
        return f"product_id={d.get('product_id')} title={title} features={n_f} benefits={n_b} faq={n_faq}"
    except Exception:
        return str(d)


def parse_product_schema_json(raw: str) -> Dict[str, Any]:
    """
    AI 출력 문자열에서 JSON 블록을 추출해 파싱합니다.
    ```json ... ``` 또는 그냥 JSON 문자열을 지원합니다.
    """
    s = (raw or "").strip()
    # 코드 블록 제거
    if "```" in s:
        start = s.find("```")
        if start != -1:
            s = s[start + 3:]
            if s.lstrip().lower().startswith("json"):
                s = s[4:].lstrip()
        end = s.rfind("```")
        if end != -1:
            s = s[:end].strip()
    return json.loads(s)
