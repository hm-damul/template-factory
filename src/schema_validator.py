# -*- coding: utf-8 -*-
"""
schema_validator.py

결정론적 규칙 기반 검증: 스키마 필드 존재, 빈 섹션 금지, 최소 개수 충족.
QA Stage 1의 "Rule-based validation pass"에서 사용.
실패 시 QA Stage 1 불통과.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .product_schema import (
    MIN_BENEFITS,
    MIN_FAQ,
    MIN_FEATURES,
    MIN_TITLE_LENGTH,
    MIN_DESCRIPTION_LENGTH,
    MIN_VALUE_PROP_LENGTH,
    MIN_BENEFIT_LENGTH,
    MIN_FAQ_A_LENGTH,
    get_nested,
    required_paths,
)


class ValidationResult:
    """규칙 기반 검증 결과."""

    def __init__(self, passed: bool, errors: List[str]):
        self.passed = passed
        self.errors = list(errors) if errors else []

    def to_dict(self) -> Dict[str, Any]:
        return {"passed": self.passed, "errors": self.errors}


def validate_schema_structure(data: Dict[str, Any]) -> List[str]:
    """
    모든 스키마 필드가 존재하는지 검사합니다.
    반환: 에러 메시지 리스트 (비어 있으면 통과).
    """
    errors: List[str] = []
    for path in required_paths():
        val = get_nested(data, path)
        if val is None:
            errors.append(f"필수 필드 누락: {'.'.join(path)}")
    return errors


def validate_no_empty_sections(data: Dict[str, Any]) -> List[str]:
    """필수 문자열/리스트 필드가 비어 있지 않은지 및 최소 길이를 준수하는지 검사합니다."""
    errors: List[str] = []

    # 문자열 필드 및 최소 길이 검사
    string_checks = [
        (["product_id"], 1),
        (["title"], MIN_TITLE_LENGTH),
        (["target_customer"], 10),
        (["value_proposition"], MIN_VALUE_PROP_LENGTH),
        (["sections", "hero", "headline"], 10),
        (["sections", "hero", "subheadline"], 20),
        (["sections", "problem", "description"], MIN_DESCRIPTION_LENGTH),
        (["sections", "solution", "description"], MIN_DESCRIPTION_LENGTH),
        (["sections", "pricing", "tier_name"], 2),
        (["sections", "pricing", "price"], 1),
        (["sections", "cta", "text"], 5),
    ]

    for path, min_len in string_checks:
        val = get_nested(data, path)
        if val is not None and isinstance(val, str):
            stripped = val.strip()
            if not stripped:
                errors.append(f"빈 문자열: {'.'.join(path)}")
            elif len(stripped) < min_len:
                errors.append(f"너무 짧은 내용: {'.'.join(path)} (최소 {min_len}자 필요, 현재 {len(stripped)}자)")

    # features, benefits: 개수는 아래에서 검사
    features = get_nested(data, ["sections", "features"])
    if features is not None:
        if not isinstance(features, list):
            errors.append("sections.features는 배열이어야 합니다.")
        else:
            for i, f in enumerate(features):
                if not (f or "").strip():
                    errors.append(f"sections.features[{i}]가 비어 있습니다.")

    benefits = get_nested(data, ["sections", "benefits"])
    if benefits is not None:
        if not isinstance(benefits, list):
            errors.append("sections.benefits는 배열이어야 합니다.")
        else:
            for i, b in enumerate(benefits):
                if len((b or "").strip()) < MIN_BENEFIT_LENGTH:
                    errors.append(f"sections.benefits[{i}]가 너무 짧습니다 (최소 {MIN_BENEFIT_LENGTH}자).")

    faq = get_nested(data, ["sections", "faq"])
    if faq is not None and not isinstance(faq, list):
        errors.append("sections.faq는 배열이어야 합니다.")

    return errors


def validate_min_counts(data: Dict[str, Any]) -> List[str]:
    """최소 개수 및 품질 검사: features >= 3, benefits >= 3, FAQ >= 3."""
    errors: List[str] = []
    features = get_nested(data, ["sections", "features"]) or []
    benefits = get_nested(data, ["sections", "benefits"]) or []
    faq = get_nested(data, ["sections", "faq"]) or []

    if len(features) < MIN_FEATURES:
        errors.append(f"features 최소 {MIN_FEATURES}개 필요 (현재 {len(features)}개)")
    if len(benefits) < MIN_BENEFITS:
        errors.append(f"benefits 최소 {MIN_BENEFITS}개 필요 (현재 {len(benefits)}개)")
    if len(faq) < MIN_FAQ:
        errors.append(f"FAQ 최소 {MIN_FAQ}개 필요 (현재 {len(faq)}개)")

    # FAQ 각 항목에 q, a 존재 및 최소 길이 검사
    for i, item in enumerate(faq):
        if not isinstance(item, dict):
            errors.append(f"faq[{i}]는 객체여야 합니다.")
        else:
            q = (item.get("q") or "").strip()
            a = (item.get("a") or "").strip()
            if not q:
                errors.append(f"faq[{i}].q가 비어 있습니다.")
            if len(a) < MIN_FAQ_A_LENGTH:
                errors.append(f"faq[{i}].a가 너무 짧습니다 (최소 {MIN_FAQ_A_LENGTH}자 필요, 현재 {len(a)}자).")

    return errors


def validate_cta_exists(data: Dict[str, Any]) -> List[str]:
    """CTA 섹션 존재 및 text 비어 있지 않음 (이미 validate_no_empty_sections에서 검사)."""
    cta = get_nested(data, ["sections", "cta"])
    if cta is None:
        return ["sections.cta 필드가 없습니다."]
    if not isinstance(cta, dict):
        return ["sections.cta는 객체여야 합니다."]
    if not (cta.get("text") or "").strip():
        return ["sections.cta.text가 비어 있습니다."]
    return []


def run_rule_based_validation(data: Dict[str, Any]) -> ValidationResult:
    """
    모든 결정론적 규칙 기반 검증을 실행합니다.
    실패 시 QA Stage 1 Block.
    """
    all_errors: List[str] = []
    all_errors.extend(validate_schema_structure(data))
    all_errors.extend(validate_no_empty_sections(data))
    all_errors.extend(validate_min_counts(data))
    all_errors.extend(validate_cta_exists(data))
    return ValidationResult(passed=len(all_errors) == 0, errors=all_errors)
