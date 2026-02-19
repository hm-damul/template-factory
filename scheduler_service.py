# -*- coding: utf-8 -*-
"""
scheduler_service.py

목적:
- 완전 무인 운영: 일정 간격으로 auto_pilot.py를 실행
- 대시보드에서 start/stop 가능하도록 스레드 기반 서비스 제공

주의:
- Windows에서 subprocess 실행을 안전하게 처리.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class SchedulerConfig:
    enabled: bool = False
    interval_minutes: int = 180
    max_products_per_day: int = 2
    languages: str = "en,ko"


class SchedulerService:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.cfg_path = project_root / "data" / "scheduler.json"
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.cfg = self.load()

    def load(self) -> SchedulerConfig:
        if self.cfg_path.exists():
            try:
                js = json.loads(
                    self.cfg_path.read_text(encoding="utf-8", errors="ignore")
                )
                return SchedulerConfig(
                    enabled=bool(js.get("enabled", False)),
                    interval_minutes=int(js.get("interval_minutes", 180)),
                    max_products_per_day=int(js.get("max_products_per_day", 2)),
                    languages=str(js.get("languages", "en,ko")),
                )
            except Exception:
                pass
        return SchedulerConfig()

    def save(self) -> None:
        self.cfg_path.parent.mkdir(parents=True, exist_ok=True)
        self.cfg_path.write_text(
            json.dumps(self.cfg.__dict__, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self.cfg.enabled = True
        self.save()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.cfg.enabled = False
        self.save()
        self._stop.set()

    def status(self) -> dict:
        return {
            "enabled": self.cfg.enabled,
            "interval_minutes": self.cfg.interval_minutes,
            "max_products_per_day": self.cfg.max_products_per_day,
            "languages": self.cfg.languages,
            "running": bool(self._thread and self._thread.is_alive()),
        }

    def update(
        self, interval_minutes: int, max_products_per_day: int, languages: str
    ) -> None:
        self.cfg.interval_minutes = int(interval_minutes)
        self.cfg.max_products_per_day = int(max_products_per_day)
        self.cfg.languages = str(languages)
        self.save()

    def _run_loop(self) -> None:
        last_day = time.strftime("%Y-%m-%d")
        count_today = 0
        while not self._stop.is_set():
            day = time.strftime("%Y-%m-%d")
            if day != last_day:
                last_day = day
                count_today = 0

            if count_today < self.cfg.max_products_per_day:
                # auto_pilot 실행
                try:
                    cmd = [
                        "python",
                        "auto_pilot.py",
                        "--batch",
                        "1",
                        "--languages",
                        self.cfg.languages,
                    ]
                    subprocess.run(cmd, cwd=str(self.project_root), check=False)
                except Exception:
                    pass
                count_today += 1

            # interval sleep
            for _ in range(max(1, self.cfg.interval_minutes * 60)):
                if self._stop.is_set():
                    break
                time.sleep(1)
