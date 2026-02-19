# -*- coding: utf-8 -*-
"""
Instagram Graph API 구조(스켈레톤):
- 실제 업로드는 OAuth + media container + publish 단계 필요
- 키 없으면 mock 로그로 대체
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict


def post_caption(caption: str, log_dir: Path) -> Dict:
    log_dir.mkdir(parents=True, exist_ok=True)
    p = log_dir / "instagram_mock.log"
    p.write_text(
        (p.read_text(encoding="utf-8", errors="ignore") if p.exists() else "")
        + f"\\nPOST: {caption}\\n",
        encoding="utf-8",
    )
    return {"ok": True, "provider": "instagram", "mode": "mock"}
