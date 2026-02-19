# -*- coding: utf-8 -*-
"""
qc_engine.py

목적:
- 생성된 제품 Markdown/자료의 "실전 판매 가능성"을 휴리스틱으로 점수화(0~100)
- 90점 미만이면 자동 재생성(오케스트레이터에서 반복 호출)

주의:
- 본 QC는 "정량적 근거 기반 휴리스틱"입니다. (LLM 없이도 동작)
- 실제로는 LLM/전문 리뷰 기반 점수와 혼합하는 것이 가장 강력합니다.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

RE_NUMBER = re.compile(r"\b\d+(\.\d+)?%?\b")
RE_TABLE = re.compile(r"^\|.+\|$", re.M)


REQUIRED_SECTIONS = [
    "Executive Overview",
    "Strategic Foundation",
    "Step-by-step Implementation Framework",
    "Case Study",
    "Tool Stack",
    "Execution Checklist",
    "Advanced Strategies",
    "Troubleshooting Matrix",
    "30/60/90 Day Roadmap",
    "Quick Start Guide",
    "Self-Assessment Checklist",
    "Glossary",
    "Policy Templates",
    "Support Macros",
]


@dataclass
class QCResult:
    score: int
    details: Dict[str, int]
    missing_sections: List[str]


def _count_numbers(text: str) -> int:
    return len(RE_NUMBER.findall(text))


def _has_table(text: str) -> bool:
    return bool(RE_TABLE.search(text or ""))


def _section_presence(text: str) -> Tuple[int, List[str]]:
    missing = []
    present = 0
    for sec in REQUIRED_SECTIONS:
        if sec.lower() in (text or "").lower():
            present += 1
        else:
            missing.append(sec)
    return present, missing


def score_markdown(md_text: str) -> QCResult:
    """
    점수 구성(총 100):
    - 섹션 커버리지 35
    - 분량(깊이) 20
    - 숫자/지표 15
    - 체크리스트/워크플로우 15
    - 테이블/템플릿/매크로 15
    """
    text = md_text or ""
    details: Dict[str, int] = {}

    # 1) 섹션 커버리지
    present, missing = _section_presence(text)
    coverage_ratio = present / max(1, len(REQUIRED_SECTIONS))
    s_coverage = int(round(35 * coverage_ratio))
    details["section_coverage"] = s_coverage

    # 2) 분량
    words = len(re.findall(r"\w+", text))
    # 4,000 단어 이상이면 만점(20), 2,000이면 15, 1,000이면 10, 500이면 5
    if words >= 4000:
        s_depth = 20
    elif words >= 2000:
        s_depth = 15
    elif words >= 1000:
        s_depth = 10
    elif words >= 500:
        s_depth = 5
    else:
        s_depth = 2
    details["depth_words"] = s_depth

    # 3) 숫자/지표
    nums = _count_numbers(text)
    if nums >= 120:
        s_metrics = 15
    elif nums >= 70:
        s_metrics = 12
    elif nums >= 40:
        s_metrics = 9
    elif nums >= 20:
        s_metrics = 6
    else:
        s_metrics = 3
    details["metrics_numbers"] = s_metrics

    # 4) 워크플로우/체크리스트(마커 기반)
    checklist_hits = len(
        re.findall(
            r"(^- \[ \]|\b체크리스트\b|\bworkflow\b|\b단계\b|\bstep\b)",
            text,
            re.I | re.M,
        )
    )
    if checklist_hits >= 60:
        s_workflows = 15
    elif checklist_hits >= 35:
        s_workflows = 12
    elif checklist_hits >= 20:
        s_workflows = 9
    elif checklist_hits >= 10:
        s_workflows = 6
    else:
        s_workflows = 3
    details["workflows_checklists"] = s_workflows

    # 5) 테이블/템플릿/매크로
    templates_hits = len(
        re.findall(
            r"\btemplate\b|\b매크로\b|\bpolicy\b|\b정책\b|\b스크립트\b", text, re.I
        )
    )
    has_table = _has_table(text)
    s_templates = 0
    if has_table:
        s_templates += 6
    if templates_hits >= 60:
        s_templates += 9
    elif templates_hits >= 30:
        s_templates += 7
    elif templates_hits >= 15:
        s_templates += 5
    else:
        s_templates += 3
    s_templates = min(15, s_templates)
    details["templates_tables"] = s_templates

    total = int(sum(details.values()))
    total = max(0, min(100, total))
    return QCResult(score=total, details=details, missing_sections=missing)


def write_quality_report(output_dir: Path, result: QCResult, attempts: int) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "score": result.score,
        "details": result.details,
        "missing_sections": result.missing_sections,
        "attempts": attempts,
    }
    path = output_dir / "quality_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
