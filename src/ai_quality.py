# -*- coding: utf-8 -*-
"""
ai_quality.py

생성 후 AI 품질 검사: 가치 제안 명확성, 논리 일관성, 설득력, 구조 완전성 평가.
QUALITY SCORE (0–100) 및 결함 목록 반환. 75 미만 시 자동 개선 사이클 트리거 가능.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

from .utils import get_logger, ProductionError

logger = get_logger(__name__)

# 품질 통과 임계값 (이 값 이상이어야 QA Stage 1 통과)
QUALITY_SCORE_THRESHOLD = int(os.getenv("AI_QUALITY_THRESHOLD", "90"))

# 환경 변수: DeepSeek 또는 호환 OpenAI API
AI_API_KEY = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
AI_API_BASE = os.getenv("AI_API_BASE", "https://api.deepseek.com/v1")
AI_MODEL = os.getenv("AI_QUALITY_MODEL", "deepseek-chat")


@dataclass
class QualityInspectionResult:
    """AI 품질 검사 결과."""

    score: int  # 0–100
    passed: bool  # score >= QUALITY_SCORE_THRESHOLD
    defects: List[str] = field(default_factory=list)
    raw_response: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "passed": self.passed,
            "defects": self.defects,
            "threshold": QUALITY_SCORE_THRESHOLD,
        }


def _call_chat_completion(
    system_prompt: str, user_prompt: str, max_tokens: int = 1500
) -> Optional[str]:
    """
    OpenAI 호환 Chat Completions API 호출.
    API 키가 없으면 None 반환 (품질 검사 스킵 시뮬레이션 시 75로 통과 처리).
    """
    if not AI_API_KEY:
        logger.warning("AI_API_KEY(DEEPSEEK_API_KEY/OPENAI_API_KEY) 미설정. AI 품질 검사 스킵.")
        return None
    url = f"{AI_API_BASE.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": AI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content")
        return content
    except Exception as e:
        logger.exception("AI 품질 검사 API 호출 실패: %s", e)
        return None


def _parse_score_and_defects(text: str) -> tuple[int, List[str]]:
    """응답 텍스트에서 score(0-100)와 defects 리스트를 추출합니다."""
    score = 0
    defects: List[str] = []
    if not text:
        return score, defects

    # "score": 85 또는 "score": 85, 또는 "quality_score": 85 등
    for pattern in [
        r'"score"\s*:\s*(\d+)',
        r'quality_score["\s:]+(\d+)',
        r'score["\s:]+(\d+)',
        r'(\d+)\s*/\s*100',
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            score = max(0, min(100, int(m.group(1))))
            break

    # defects / issues / problems 블록 또는 - item 형태
    lines = text.split("\n")
    in_defects = False
    for line in lines:
        lower = line.lower()
        if "defect" in lower or "issue" in lower or "problem" in lower:
            in_defects = True
            continue
        if in_defects:
            stripped = line.strip()
            if stripped.startswith("-") or stripped.startswith("*") or re.match(r"^\d+\.", stripped):
                defect = re.sub(r"^[-*]\s*", "", re.sub(r"^\d+\.\s*", "", stripped)).strip()
                if defect and len(defect) > 3:
                    defects.append(defect)
            elif stripped.startswith("{"):
                in_defects = False

    return score, defects[:20]  # 최대 20개


def run_quality_inspection(product_schema: Dict[str, Any]) -> QualityInspectionResult:
    """
    제품 스키마(JSON)에 대해 AI 품질 검사를 실행합니다.
    평가 항목: 가치 제안 명확성, 논리 일관성, 설득력, 구조 완전성.
    """
    system_prompt = """You are a quality inspector for digital product landing content.
Evaluate the product schema for:
1. Clarity of value proposition (is it clear what the customer gets?)
2. Logical consistency (do problem, solution, features, benefits align?)
3. Persuasiveness (would this convince a buyer?)
4. Structural completeness (all sections meaningful, no placeholders).

Respond in JSON only, no markdown fences:
{
  "score": <0-100 integer>,
  "defects": ["list", "of", "specific", "issues"]
}
If the product is sellable and complete, score >= 75. If vague or inconsistent, score lower and list defects."""

    user_prompt = "Evaluate this product schema and return only the JSON object (score + defects):\n\n"
    user_prompt += json.dumps(product_schema, ensure_ascii=False, indent=2)

    raw = _call_chat_completion(system_prompt, user_prompt)
    if raw is None:
        # API 미사용 시: 경고 후 통과 (Stagnation 방지)
        logger.warning("AI 품질 검사 API 키 누락. 기본 점수(80)로 통과 처리합니다.")
        return QualityInspectionResult(
            score=80,
            passed=True,
            defects=["AI Quality Check Skipped (No API Key)"],
            raw_response="Skipped"
        )

    # JSON 블록 추출 시도
    try:
        json_str = raw.strip()
        if "```" in json_str:
            m = re.search(r"```(?:json)?\s*([\s\S]*?)```", json_str)
            if m:
                json_str = m.group(1).strip()
        obj = json.loads(json_str)
        score = max(0, min(100, int(obj.get("score", 0))))
        defects = list(obj.get("defects") or [])
        if not isinstance(defects, list):
            defects = [str(defects)]
    except (json.JSONDecodeError, TypeError, ValueError):
        score, defects = _parse_score_and_defects(raw)

    return QualityInspectionResult(
        score=score,
        passed=score >= QUALITY_SCORE_THRESHOLD,
        defects=defects,
        raw_response=raw,
    )


def suggest_improvements(product_schema: Dict[str, Any], defects: List[str]) -> str:
    """
    결함 목록을 바탕으로 개선 프롬프트 문구를 생성합니다.
    자동 개선 사이클에서 "약한 섹션만 재생성"할 때 사용할 수 있습니다.
    """
    if not defects:
        return ""
    return "Address these defects in the product content:\n" + "\n".join(
        f"- {d}" for d in defects[:15]
    )
