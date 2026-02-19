# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import time
from typing import Callable, Dict


def is_mock_mode() -> bool:
    return os.getenv("SOCIAL_MOCK", "1").strip() != "0"


def with_retry(fn: Callable[[], Dict], tries: int = 3, sleep_sec: int = 2) -> Dict:
    last = None
    for _ in range(max(1, tries)):
        try:
            return fn()
        except Exception as e:
            last = e
            time.sleep(sleep_sec)
    return {"ok": False, "error": str(last) if last else "unknown"}
