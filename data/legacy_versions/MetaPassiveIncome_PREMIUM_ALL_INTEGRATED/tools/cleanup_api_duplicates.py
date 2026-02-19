# -*- coding: utf-8 -*-
"""
tools/cleanup_api_duplicates.py
목적:
- 과거 버그로 생성된 중복 API 경로를 정리한다.
  예) api/pay/api/pay/check.py 같은 "중첩" 폴더

실행(Windows PowerShell):
  python tools\cleanup_api_duplicates.py

동작:
- 프로젝트 루트 기준으로 아래 경로가 존재하면 삭제한다.
  - api/pay/api/  (전체 폴더 삭제)
"""

from __future__ import annotations

import shutil
from pathlib import Path


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    bad_dir = project_root / "api" / "pay" / "api"

    print(f"[cleanup] project_root = {project_root}")

    if bad_dir.exists() and bad_dir.is_dir():
        print(f"[cleanup] removing duplicated api folder: {bad_dir}")
        shutil.rmtree(str(bad_dir))
        print("[cleanup] OK removed.")
    else:
        print("[cleanup] nothing to remove. (api/pay/api does not exist)")

    good_start = project_root / "api" / "pay" / "start.py"
    good_check = project_root / "api" / "pay" / "check.py"

    print(
        f"[cleanup] expected: {good_start} -> {'OK' if good_start.exists() else 'MISSING'}"
    )
    print(
        f"[cleanup] expected: {good_check} -> {'OK' if good_check.exists() else 'MISSING'}"
    )


if __name__ == "__main__":
    main()
