# -*- coding: utf-8 -*-
"""
quality_audit.py

목적:
- 섹션 단위로 "깊이/구조/실무성" 점수를 계산하여 기준 미달이면 재생성하도록 한다.
- 외부 LLM 없이도 사용할 수 있도록 정적 휴리스틱 기반.

점수 구성(0~100):
- Depth: 단어 수, 문단 수, 예시 수, 숫자 포함 여부
- Structure: 서브헤더 수, 불릿/번호 목록의 존재, 콜아웃 존재
- Practicality: 체크리스트/워크플로우/액션 지시문 포함 여부

주의:
- 점수는 '상대적'이며, 목표는 "얕은 요약"을 걸러내는 것이다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from premium_content_engine import Section, Subsection


@dataclass(frozen=True)
class AuditResult:
    ok: bool
    score: int
    details: List[str]


_WORD_RE = re.compile(r"[A-Za-z0-9]+")
_NUM_RE = re.compile(r"\d")

_BANNED_PHRASES = [
    "as an ai",
    "i cannot",
    "in conclusion",
    "overall",
    "this guide will",
    "high level",
    "to summarize",
    "in summary",
    "it is important to note",
    "various",
    "some",
]
_ACTION_VERBS = [
    "track",
    "log",
    "ship",
    "deploy",
    "measure",
    "build",
    "create",
    "write",
    "test",
    "add",
    "verify",
    "instrument",
    "optimize",
    "iterate",
    "configure",
    "implement",
]


def _count_words(text: str) -> int:
    return len(_WORD_RE.findall(text or ""))


def _has_numbers(text: str) -> bool:
    return bool(_NUM_RE.search(text or ""))


def _contains_action_language(text: str) -> bool:
    t = (text or "").lower()
    return any(v in t for v in _ACTION_VERBS)


def _subsection_text(sub: Subsection) -> str:
    parts: List[str] = []
    parts.extend(sub.paragraphs)
    parts.extend(sub.bullets)
    parts.extend(sub.numbered_steps)
    for c in sub.callouts:
        parts.append(c.title)
        parts.append(c.body)
    return "\n".join(parts)


def score_section(section: Section) -> AuditResult:
    """
    섹션 품질 점수(휴리스틱).
    - 기준은 "판매 가능한 유료 가이드"로서 최소한의 실무 구조를 갖췄는지.
    """
    details: List[str] = []

    subs = section.subsections or []
    sub_count = len(subs)

    word_count = 0
    para_count = 0
    bullet_count = 0
    step_count = 0
    callout_count = 0
    has_numbers = False
    num_count = 0
    banned_hits: List[str] = []
    action_lang = False

    for sub in subs:
        txt = _subsection_text(sub)
        word_count += _count_words(txt)
        para_count += len([p for p in sub.paragraphs if (p or "").strip()])
        bullet_count += len([b for b in sub.bullets if (b or "").strip()])
        step_count += len([s for s in sub.numbered_steps if (s or "").strip()])
        callout_count += len(sub.callouts or [])
        has_numbers = has_numbers or _has_numbers(txt)
        action_lang = action_lang or _contains_action_language(txt)

    # Depth score
    # 목표: 섹션당 충분한 분량(휴리스틱)
    depth = 0
    if word_count >= 900:
        depth += 40
    elif word_count >= 650:
        depth += 32
    elif word_count >= 450:
        depth += 24
    else:
        depth += 14

    if para_count >= 10:
        depth += 10
    elif para_count >= 6:
        depth += 7
    else:
        depth += 3

    if has_numbers:
        depth += 10
    else:
        depth += 0

    # Structure score
    structure = 0
    if sub_count >= 5:
        structure += 20
    elif sub_count >= 3:
        structure += 14
    else:
        structure += 8

    if bullet_count >= 10:
        structure += 10
    elif bullet_count >= 6:
        structure += 7
    else:
        structure += 3

    if step_count >= 6:
        structure += 10
    elif step_count >= 3:
        structure += 7
    else:
        structure += 3

    if callout_count >= 2:
        structure += 10
    elif callout_count >= 1:
        structure += 6
    else:
        structure += 0

    # Practicality score
    practicality = 0
    practicality += 10 if action_lang else 0
    # checklist/workflow hint
    t = (section.title or "").lower()
    if "checklist" in t or "framework" in t or "troubleshoot" in t or "roadmap" in t:
        practicality += 10
    else:
        practicality += 6

    score = min(100, depth + structure + practicality)

    if word_count < 450:
        details.append(f"Low word count ({word_count}).")
    if bullet_count < 4:
        details.append(f"Low bullet density ({bullet_count}).")
    if step_count < 2:
        details.append(f"Low step density ({step_count}).")
    if callout_count < 1:
        details.append("No callouts (Expert Note/Pro Tip).")
    if not has_numbers:
        details.append("No numerical examples found.")
    if not action_lang:
        details.append("No action-oriented language detected.")

    # Anti-fluff: ban common AI-summary patterns
    if banned_hits:
        uniq = sorted(set(banned_hits))
        details.append("Banned phrase(s) detected: " + ", ".join(uniq))
        # hard penalty
        score -= min(20, 4 * len(uniq))

    # Numbers: premium sections should contain concrete metrics/examples
    if num_count < 8:
        details.append(f"Too few numeric anchors (found {num_count}, need >= 8).")
        score -= 10
    # Minimum bar: 80 for premium
    ok = score >= 80
    details.append(
        f"Words={word_count}, paras={para_count}, bullets={bullet_count}, steps={step_count}, callouts={callout_count}"
    )
    return AuditResult(ok=ok, score=score, details=details)
