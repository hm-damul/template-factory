# -*- coding: utf-8 -*-
"""
Reddit API 구조(스켈레톤):
- 실제 업로드는 praw 라이브러리 및 Client ID/Secret 필요
- 키 없으면 mock 로그
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict


def post_text(text: str, log_dir: Path) -> Dict:
    log_dir.mkdir(parents=True, exist_ok=True)
    p = log_dir / "reddit_mock.log"
    p.write_text(
        (p.read_text(encoding="utf-8", errors="ignore") if p.exists() else "")
        + f"\nPOST: {text}\n",
        encoding="utf-8",
    )
    return {"ok": True, "provider": "reddit", "mode": "mock"}
