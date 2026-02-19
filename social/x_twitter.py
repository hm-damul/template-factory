# -*- coding: utf-8 -*-
"""
X(Twitter) API 구조:
- 환경변수 X_BEARER_TOKEN이 있으면 실제 호출(간단 텍스트 게시)
- 없으면 mock 모드로 로그만 남김
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
from typing import Dict

import tweepy

from .common import is_mock_mode, with_retry


def post_text(text: str, log_dir: Path) -> Dict:
    log_dir.mkdir(parents=True, exist_ok=True)

    # 필수 키 확인
    ck = os.getenv("X_CONSUMER_KEY", "").strip()
    cs = os.getenv("X_CONSUMER_SECRET", "").strip()
    at = os.getenv("X_ACCESS_TOKEN", "").strip()
    as_ = os.getenv("X_ACCESS_TOKEN_SECRET", "").strip()
    
    # 예외: 예전 방식인 X_BEARER_TOKEN만 있어도 일단 시도 (읽기 전용일 가능성 높음)
    bt = os.getenv("X_BEARER_TOKEN", "").strip()

    if is_mock_mode() or not (ck and cs and at and as_):
        # API 키가 없으면 mock로 동작
        p = log_dir / "x_mock.log"
        p.write_text(
            (p.read_text(encoding="utf-8", errors="ignore") if p.exists() else "")
            + f"\n[{_utc_iso()}] POST: {text}\n",
            encoding="utf-8",
        )
        if not is_mock_mode():
            return {"ok": True, "provider": "x", "mode": "mock", "note": "Missing API keys"}
        return {"ok": True, "provider": "x", "mode": "mock"}

    def _call():
        # X API v2 (Tweepy Client)
        client = tweepy.Client(
            bearer_token=bt if bt else None,
            consumer_key=ck,
            consumer_secret=cs,
            access_token=at,
            access_token_secret=as_,
        )
        try:
            response = client.create_tweet(text=text)
            return {"ok": True, "provider": "x", "mode": "real", "resp": str(response.data)}
        except tweepy.errors.HTTPException as e:
            # 402 Payment Required: Out of credits
            if e.response is not None and e.response.status_code == 402:
                return {"ok": False, "provider": "x", "error": "CREDIT_EXHAUSTED", "msg": str(e)}
            raise e # retry logic will catch other exceptions

    r = with_retry(_call, tries=2, sleep_sec=2)
    if not r.get("ok"):
        p = log_dir / "x_error.log"
        p.write_text(
            (p.read_text(encoding="utf-8", errors="ignore") if p.exists() else "")
            + f"\n[{_utc_iso()}] ERROR: {r}\n",
            encoding="utf-8",
        )
    return r


def _utc_iso() -> str:
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
