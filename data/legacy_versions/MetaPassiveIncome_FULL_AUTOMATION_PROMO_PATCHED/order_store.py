# -*- coding: utf-8 -*-
"""
order_store.py

목적:
- 주문(orders)을 저장/조회하는 단일 인터페이스 제공.
- 로컬에서는 data/orders.json 파일에 저장(원자적 저장).
- 배포(Vercel)에서는 파일 쓰기가 영속적이지 않으므로,
  UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN 이 있으면 Upstash Redis REST를 사용한다.
  (없으면 로컬과 동일한 파일 저장을 시도하되, Vercel에서는 재시작 시 유실될 수 있음)

주문 상태:
- pending
- paid
- expired
- failed

주의:
- 이 프로젝트는 "지갑 결제" 기반이므로, 다운로드는 반드시 paid 상태에서만 허용한다.
"""

from __future__ import annotations

import json  # JSON 저장
import os  # 환경변수
import time  # 타임스탬프
import uuid  # order_id
from dataclasses import asdict, dataclass  # 구조체
from pathlib import Path  # 경로
from typing import Any, Dict, List, Optional  # 타입

import requests  # Upstash REST 호출


@dataclass
class Order:
    """주문 데이터(반드시 JSON 직렬화 가능한 타입만 사용)."""

    order_id: str
    product_id: str
    amount: float
    currency: str
    status: str  # pending/paid/expired/failed
    created_at: str
    provider: str  # nowpayments|simulated
    provider_payment_id: str = ""  # NOWPayments payment_id 등
    provider_invoice_url: str = ""  # 결제 페이지 URL(있으면)
    meta: Dict[str, Any] | None = None


def _utc_iso() -> str:
    """UTC ISO 문자열."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _atomic_write_json(path: Path, obj) -> None:
    """원자적으로 JSON 파일을 저장."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


def _read_json(path: Path, default):
    """JSON 파일을 읽고 없으면 default 반환."""
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


class FileOrderStore:
    """로컬 파일 기반 주문 저장소."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.path = self.data_dir / "orders.json"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            _atomic_write_json(self.path, [])

    def list_orders(self) -> List[Dict[str, Any]]:
        return _read_json(self.path, [])

    def get(self, order_id: str) -> Optional[Dict[str, Any]]:
        for o in self.list_orders():
            if str(o.get("order_id")) == str(order_id):
                return o
        return None

    def upsert(self, order: Order) -> Dict[str, Any]:
        orders = self.list_orders()
        found = False
        for i, o in enumerate(orders):
            if str(o.get("order_id")) == order.order_id:
                orders[i] = asdict(order)
                found = True
                break
        if not found:
            orders.append(asdict(order))
        _atomic_write_json(self.path, orders)
        return asdict(order)

    def update_status(self, order_id: str, status: str) -> Optional[Dict[str, Any]]:
        orders = self.list_orders()
        for i, o in enumerate(orders):
            if str(o.get("order_id")) == str(order_id):
                o["status"] = status
                orders[i] = o
                _atomic_write_json(self.path, orders)
                return o
        return None


class UpstashOrderStore:
    """Upstash Redis REST 기반 주문 저장소."""

    def __init__(self, url: str, token: str, namespace: str = "mpif") -> None:
        self.url = url.rstrip("/")
        self.token = token
        self.ns = namespace

    def _key(self, order_id: str) -> str:
        return f"{self.ns}:order:{order_id}"

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def get(self, order_id: str) -> Optional[Dict[str, Any]]:
        r = requests.get(
            f"{self.url}/get/{self._key(order_id)}", headers=self._headers(), timeout=10
        )
        r.raise_for_status()
        data = r.json()
        val = data.get("result")
        if not val:
            return None
        if isinstance(val, str):
            return json.loads(val)
        return val

    def upsert(self, order: Order) -> Dict[str, Any]:
        key = self._key(order.order_id)
        value = json.dumps(asdict(order), ensure_ascii=False)
        r = requests.post(
            f"{self.url}/set/{key}",
            headers=self._headers(),
            data=value.encode("utf-8"),
            timeout=10,
        )
        r.raise_for_status()
        return asdict(order)

    def update_status(self, order_id: str, status: str) -> Optional[Dict[str, Any]]:
        cur = self.get(order_id)
        if not cur:
            return None
        cur["status"] = status
        key = self._key(order_id)
        r = requests.post(
            f"{self.url}/set/{key}",
            headers=self._headers(),
            data=json.dumps(cur, ensure_ascii=False).encode("utf-8"),
            timeout=10,
        )
        r.raise_for_status()
        return cur

    def list_orders(self) -> List[Dict[str, Any]]:
        # Upstash REST의 KEYS는 제한될 수 있어, 대시보드에서는 파일 저장소를 권장.
        # 여기서는 최소 구현: 지원하지 않음.
        return []


def get_order_store(project_root: Path):
    """환경에 맞는 주문 저장소를 선택한다."""
    up_url = os.getenv("UPSTASH_REDIS_REST_URL", "").strip()
    up_token = os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip()
    if up_url and up_token:
        return UpstashOrderStore(url=up_url, token=up_token, namespace="mpif")
    return FileOrderStore(data_dir=project_root / "data")


def new_order_id() -> str:
    """order_id 생성."""
    return uuid.uuid4().hex
