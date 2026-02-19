
from src.ledger_manager import LedgerManager
import json

def check_fail_reasons():
    lm = LedgerManager()
    failed = lm.get_products_by_status("PIPELINE_FAILED")
    
    reasons = {}
    for p in failed:
        metadata = p.get('metadata', {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except:
                metadata = {}
        
        err = metadata.get('error', 'Unknown')
        reasons[err] = reasons.get(err, 0) + 1
        
    print("Failure Reasons:")
    for err, count in reasons.items():
        print(f"  {err}: {count}")

if __name__ == "__main__":
    check_fail_reasons()
