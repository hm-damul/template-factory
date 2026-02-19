
import sys
import os
import json
from pathlib import Path

# Add project root
sys.path.append(os.getcwd())

from src.ledger_manager import LedgerManager

def debug_qa_status():
    lm = LedgerManager()
    products = lm.get_all_products()
    
    print(f"Total products: {len(products)}")
    
    counts = {}
    qa_counts = {}
    
    for p in products:
        status = p.get("status")
        counts[status] = counts.get(status, 0) + 1
        
        # Simulation of dashboard_server.py logic
        qa_status = "Pending"
        if status == "PUBLISHED":
            qa_status = "Passed"
        elif status == "PROMOTED":
            qa_status = "Published & Promoted"
        elif "QA2_PASSED" in str(status):
            qa_status = "Passed (Ready to Publish)"
        elif "QA1_PASSED" in str(status):
            qa_status = "Content Verified"
        elif "QA" in str(status) and "FAILED" in str(status):
            qa_status = "Failed"
            
        qa_counts[qa_status] = qa_counts.get(qa_status, 0) + 1
        
        if qa_status == "Pending" and status in ["PROMOTED", "PUBLISHED"]:
            print(f"MISMATCH: ID={p['id']}, Status={status}, QA={qa_status}")

    print("\nStatus Counts:")
    print(json.dumps(counts, indent=2))
    
    print("\nQA Status Counts:")
    print(json.dumps(qa_counts, indent=2))

if __name__ == "__main__":
    debug_qa_status()
