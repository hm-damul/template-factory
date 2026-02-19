# -*- coding: utf-8 -*-
"""
translation_engine.py

목적:
- 제품 산출물(마크다운/요약문/홍보문 등)을 다국어로 변환
- 키가 없으면 Mock(안전 대체)로 동작 -> 시스템이 멈추지 않게 함

지원(기본):
- EN, KR, ES, FR, DE, JP, CN

현재 구현:
- DeepL API (DEEPL_API_KEY가 있으면 실제 번역)
- 그 외: Mock translate (언어 태그만 붙임)
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Optional

SUPPORTED_LANGS = ["en", "ko", "es", "fr", "de", "ja", "zh"]


@dataclass
class TranslationResult:
    ok: bool
    provider: str
    text: str
    error: Optional[str] = None


def _deepl_translate(text: str, target_lang: str) -> TranslationResult:
    key = os.getenv("DEEPL_API_KEY", "").strip()
    if not key:
        return TranslationResult(
            ok=False, provider="deepl", text=text, error="missing_deepl_key"
        )

    # DeepL target codes: EN, KO, ES, FR, DE, JA, ZH
    tl = target_lang.upper()
    if tl == "ZH":
        tl = "ZH"

    data = urllib.parse.urlencode(
        {"auth_key": key, "text": text, "target_lang": tl}
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api-free.deepl.com/v2/translate", data=data, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
        js = json.loads(body)
        out = js["translations"][0]["text"]
        return TranslationResult(ok=True, provider="deepl", text=out)
    except Exception as e:
        return TranslationResult(ok=False, provider="deepl", text=text, error=str(e))


def mock_translate(text: str, target_lang: str) -> TranslationResult:
    # 시스템이 멈추지 않도록 안전 대체
    return TranslationResult(
        ok=True, provider="mock", text=f"[{target_lang}]\\n\\n{text}"
    )


def translate(text: str, target_lang: str) -> TranslationResult:
    lang = (target_lang or "").lower().strip()
    if lang not in SUPPORTED_LANGS:
        return TranslationResult(
            ok=False, provider="none", text=text, error="unsupported_lang"
        )

    # 우선 DeepL 시도
    if os.getenv("DEEPL_API_KEY", "").strip():
        r = _deepl_translate(text, lang)
        if r.ok:
            return r

    # 기본: Mock
    return mock_translate(text, lang)
