# -*- coding: utf-8 -*-
"""
auto_mode_daemon.py

완전 자동 운영 모드(Autonomous Mode):
- 일정 간격으로 제품 생성(auto_pilot single-run 호출 또는 내부 호출)
- (옵션) 생성 후 자동 배포(--deploy)
- (옵션) 생성 후 자동 Publish(ready_to_publish.json + (선택) webhook posting)
- 상태를 data/auto_mode_status.json 에 기록하여 대시보드에서 표시

실행(대시보드 버튼에서 실행되는 것을 권장):
  python auto_mode_daemon.py --interval 3600 --batch 1 --deploy 0 --publish 1

중지:
- Windows: taskkill /PID <pid> /T /F (대시보드 Stop 버튼 제공)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from promotion_dispatcher import dispatch_publish
from promotion_factory import mark_ready_to_publish

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
STATUS_PATH = DATA_DIR / "auto_mode_status.json"


def _utc_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _atomic_write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _update_status(patch: Dict[str, Any]) -> None:
    cur = _read_json(STATUS_PATH, {})
    cur.update(patch)
    cur.setdefault("updated_at", _utc_iso())
    cur["updated_at"] = _utc_iso()
    _atomic_write_json(STATUS_PATH, cur)


def _run_autopilot(batch: int, topic: str, deploy: bool) -> Dict[str, Any]:
    cmd: List[str] = [sys.executable, "auto_pilot.py", "--batch", str(int(batch))]
    if topic:
        cmd += ["--topic", topic]
    if deploy:
        cmd += ["--deploy"]

    _update_status({"phase": "running_autopilot", "last_cmd": cmd})
    p = subprocess.run(
        cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True, shell=False
    )
    out = (p.stdout or "") + "\n" + (p.stderr or "")
    return {"rc": int(p.returncode), "out": out[-20000:]}  # tail


def _discover_new_products(since_ts: float) -> List[str]:
    outputs = PROJECT_ROOT / "outputs"
    if not outputs.exists():
        return []
    new_ids: List[str] = []
    for d in outputs.iterdir():
        if not d.is_dir():
            continue
        try:
            if d.stat().st_mtime >= since_ts:
                new_ids.append(d.name)
        except Exception:
            continue
    new_ids.sort()
    return new_ids


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=3600, help="seconds between runs")
    ap.add_argument("--batch", type=int, default=1, help="products per run")
    ap.add_argument("--topic", type=str, default="", help="optional topic, blank=auto")
    ap.add_argument("--deploy", type=int, default=0, help="1 to deploy to vercel")
    ap.add_argument(
        "--publish",
        type=int,
        default=1,
        help="1 to create ready_to_publish and optionally webhook post",
    )
    ap.add_argument("--max_runs", type=int, default=0, help="0=forever")
    args = ap.parse_args()

    interval = max(60, int(args.interval))
    batch = max(1, int(args.batch))
    topic = str(args.topic or "").strip()
    deploy = bool(int(args.deploy))
    publish = bool(int(args.publish))
    max_runs = max(0, int(args.max_runs))

    _update_status(
        {
            "mode": "auto",
            "phase": "starting",
            "interval_sec": interval,
            "batch": batch,
            "topic": topic,
            "deploy": deploy,
            "publish": publish,
            "runs_done": 0,
            "last_run_at": None,
            "last_rc": None,
            "last_error": None,
            "last_products": [],
        }
    )

    runs_done = 0
    while True:
        if max_runs and runs_done >= max_runs:
            _update_status({"phase": "done", "runs_done": runs_done})
            return 0

        start_ts = time.time()
        _update_status(
            {"phase": "run_started", "last_run_at": _utc_iso(), "runs_done": runs_done}
        )

        try:
            result = _run_autopilot(batch=batch, topic=topic, deploy=deploy)
            rc = result["rc"]
            _update_status({"last_rc": rc, "last_tail": result.get("out", "")})

            # 새 제품 탐지
            new_products = _discover_new_products(since_ts=start_ts - 2)
            _update_status({"last_products": new_products})

            # publish 자동 처리
            if publish:
                _update_status({"phase": "publishing"})
                for pid in new_products:
                    try:
                        mark_ready_to_publish(
                            product_dir=(PROJECT_ROOT / "outputs" / pid), product_id=pid
                        )
                        dispatch_publish(pid)  # 설정 기반(키 없으면 파일만)
                    except Exception as e:
                        _update_status({"last_error": f"publish_error:{pid}:{e}"})

            _update_status({"phase": "sleeping"})
        except Exception as e:
            _update_status({"phase": "error", "last_error": str(e)})

        runs_done += 1
        _update_status({"runs_done": runs_done})

        # sleep (with small ticks so the status updates don't look frozen)
        end_at = time.time() + interval
        while time.time() < end_at:
            time.sleep(2)
            _update_status({"phase": "sleeping"})

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
