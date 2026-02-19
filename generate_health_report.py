import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.append(str(PROJECT_ROOT))

from src.ledger_manager import LedgerManager
from src.config import Config

def generate_report():
    lm = LedgerManager(Config.DATABASE_URL)
    
    # 최근 20개 제품 상태
    products = lm.get_all_products()
    products.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    recent = products[:20]
    
    stats = {
        "total": len(products),
        "published": len([p for p in products if p['status'] == 'PUBLISHED']),
        "waiting": len([p for p in products if p['status'] == 'WAITING_FOR_DEPLOYMENT']),
        "failed": len([p for p in products if p['status'] in ['PIPELINE_FAILED', 'CRITICAL_FAILED', 'QA_FAILED']]),
    }
    
    daemon_status = {}
    status_file = PROJECT_ROOT / "data" / "daemon_status.json"
    if status_file.exists():
        try:
            daemon_status = json.loads(status_file.read_text(encoding="utf-8"))
        except:
            pass
            
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stats": stats,
        "recent_products": [
            {
                "id": p['id'],
                "topic": p['topic'],
                "status": p['status'],
                "created_at": p['created_at']
            } for p in recent
        ],
        "daemon": daemon_status
    }
    
    output_file = PROJECT_ROOT / "data" / "health_report.json"
    output_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Health report generated: {output_file}")

if __name__ == "__main__":
    generate_report()
