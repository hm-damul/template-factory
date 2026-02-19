# -*- coding: utf-8 -*-
"""
portfolio_manager.py

목적:
- outputs/ 아래 제품들을 스캔해서
  품질(QC), 판매/주문, 산출물 존재 여부를 점수화하여 포트폴리오를 만든다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class ProductMetrics:
    product_id: str
    qc_score: int
    orders_paid: int
    revenue_usd_est: float
    has_pdf: bool
    has_promotions: bool


def _read_json(p: Path) -> Optional[dict]:
    try:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return None
    return None


def build_portfolio(project_root: Path) -> List[ProductMetrics]:
    outputs = project_root / "outputs"
    orders_js = _read_json(project_root / "data" / "orders.json") or {}
    paid_by_pid: Dict[str, int] = {}
    revenue_by_pid: Dict[str, float] = {}

    for oid, o in orders_js.items():
        try:
            if str(o.get("status", "")).lower() == "paid":
                pid = str(o.get("product_id", ""))
                paid_by_pid[pid] = paid_by_pid.get(pid, 0) + 1
                amt = float(o.get("amount") or 0.0)
                revenue_by_pid[pid] = revenue_by_pid.get(pid, 0.0) + amt
        except Exception:
            continue

    items: List[ProductMetrics] = []
    if not outputs.exists():
        return items

    for d in sorted([p for p in outputs.iterdir() if p.is_dir()]):
        pid = d.name
        qc = _read_json(d / "quality_report.json") or {}
        qc_score = int(qc.get("score") or 0)
        has_pdf = any(d.glob("*.pdf"))
        has_promotions = (d / "promotions").exists()
        paid = int(paid_by_pid.get(pid, 0))
        rev = float(revenue_by_pid.get(pid, 0.0))
        items.append(ProductMetrics(pid, qc_score, paid, rev, has_pdf, has_promotions))

    # 정렬: 매출 > 주문 > QC
    items.sort(
        key=lambda x: (x.revenue_usd_est, x.orders_paid, x.qc_score), reverse=True
    )
    return items


def write_portfolio_report(project_root: Path) -> Path:
    items = build_portfolio(project_root)
    out = []
    for it in items:
        out.append(
            {
                "product_id": it.product_id,
                "qc_score": it.qc_score,
                "orders_paid": it.orders_paid,
                "revenue_usd_est": it.revenue_usd_est,
                "has_pdf": it.has_pdf,
                "has_promotions": it.has_promotions,
            }
        )
    p = project_root / "data" / "portfolio.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return p
