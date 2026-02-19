# -*- coding: utf-8 -*-
"""
api/_security.py

목적:
- 배포(serverless)와 로컬에서 동일한 다운로드 토큰 로직을 사용하기 위한 얇은 래퍼.
- 외부 jwt 라이브러리 의존을 제거하고(payment_api의 HMAC 토큰 사용), 운영 환경에서도 안정적으로 동작하게 한다.

주의:
- 운영에서는 DOWNLOAD_TOKEN_SECRET를 반드시 설정해야 한다.
  (설정이 없으면 프로젝트 경로 기반 fallback으로 서명하므로, 배포 간 일관성이 깨질 수 있음)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

# Add project root to sys.path for Vercel
_root = str(Path(__file__).resolve().parents[1])
if _root not in sys.path:
    sys.path.insert(0, _root)

from payment_api import issue_download_token as _issue
from payment_api import verify_download_token as _verify


def _project_root() -> Path:
    # api/ 폴더 기준 상위 1단계가 프로젝트 루트(MetaPassiveIncome_FINAL)
    return Path(__file__).resolve().parents[1]


def issue_download_token(product_id: str, order_id: str, ttl_seconds: int = 900) -> str:
    """토큰 발급(server-side)."""
    return _issue(
        _project_root(),
        order_id=order_id,
        product_id=product_id,
        ttl_seconds=ttl_seconds,
        one_time=True,
    )


def verify_download_token(token: str) -> Dict[str, Any]:
    """토큰 검증."""
    return _verify(_project_root(), token)
