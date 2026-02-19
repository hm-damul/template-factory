# -*- coding: utf-8 -*-
"""
YouTube Shorts 업로드 구조(스켈레톤):
- 실제 업로드는 Google OAuth + resumable upload 필요
- 키 없으면 mock 로그
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict


def post_title(title: str, log_dir: Path) -> Dict:
    log_dir.mkdir(parents=True, exist_ok=True)
    p = log_dir / "youtube_mock.log"
    p.write_text(
        (p.read_text(encoding="utf-8", errors="ignore") if p.exists() else "")
        + f"\\nPOST: {title}\\n",
        encoding="utf-8",
    )
    return {"ok": True, "provider": "youtube", "mode": "mock"}
