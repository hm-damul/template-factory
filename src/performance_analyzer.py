# -*- coding: utf-8 -*-
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ORDERS_JSON = PROJECT_ROOT / "data" / "orders.json"
LEDGER_DB = PROJECT_ROOT / "data" / "ledger.db"
REPORTS_DIR = PROJECT_ROOT / "data" / "reports"

def analyze_performance():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    
    if not ORDERS_JSON.exists():
        return {"error": "orders.json not found"}
        
    try:
        with open(ORDERS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
            orders = data.get("orders", [])
    except Exception as e:
        return {"error": f"Failed to load orders: {e}"}

    # 1. 판매 실적 요약
    total_orders = len(orders)
    paid_orders = [o for o in orders if o.get("status") == "paid"]
    total_paid = len(paid_orders)
    
    # 평균 가격 가정 (원장에 가격 정보가 있지만, 여기선 기본값 $29 가정)
    # 실제 운영 시 ledger.db와 연동하여 정확한 수익 계산 가능
    avg_price = 29.0 
    estimated_revenue = total_paid * avg_price
    
    # 2. 일별 트렌드 (최근 30일)
    now = datetime.now()
    daily_stats = {}
    for i in range(30):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        daily_stats[day] = {"count": 0, "revenue": 0.0}
        
    for o in paid_orders:
        paid_at = o.get("paid_at", "")
        if paid_at:
            day = paid_at.split(" ")[0]
            if day in daily_stats:
                daily_stats[day]["count"] += 1
                daily_stats[day]["revenue"] += avg_price

    # 3. 제품별 실적
    product_stats = {}
    for o in paid_orders:
        pid = o.get("product_id", "unknown")
        if pid not in product_stats:
            product_stats[pid] = 0
        product_stats[pid] += 1
        
    top_products = sorted(product_stats.items(), key=lambda x: x[1], reverse=True)[:5]

    report = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "total_orders": total_orders,
            "total_paid": total_paid,
            "conversion_rate": round((total_paid / total_orders * 100), 2) if total_orders > 0 else 0,
            "estimated_revenue": estimated_revenue
        },
        "daily_trends": daily_stats,
        "top_products": [{"product_id": p[0], "sales": p[1]} for p in top_products]
    }
    
    report_path = REPORTS_DIR / f"performance_{datetime.now().strftime('%Y%m%d')}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        
    # 최신 리포트로 심볼릭 링크(또는 복사)
    latest_path = REPORTS_DIR / "latest_performance.json"
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        
    return report

if __name__ == "__main__":
    result = analyze_performance()
    print(f"Analysis Complete: {result['summary']}")
