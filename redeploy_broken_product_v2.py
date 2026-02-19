from src.auto_heal_system import AutoHealSystem
from src.ledger_manager import LedgerManager
import logging
import sys

def redeploy_broken():
    # Configure root logger to output to stdout
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    
    # Get logger for AutoHealSystem and set level
    logger = logging.getLogger("src.auto_heal_system")
    logger.setLevel(logging.INFO)
    
    print("Starting redeployment script...")
    
    lm = LedgerManager()
    ahs = AutoHealSystem()
    
    pid = "20260214-105333-global-merchant-crypto-checkou"
    print(f"Redeploying product: {pid}")
    
    # Force redeploy
    try:
        ahs._redeploy_product(pid)
        print("Redeploy 1 finished")
    except Exception as e:
        print(f"Error redeploying 1: {e}")
    
    # Also check the next one if any
    pid2 = "20260214-112651-aipassiveincomesystem"
    print(f"Redeploying product 2: {pid2}")
    try:
        ahs._redeploy_product(pid2)
        print("Redeploy 2 finished")
    except Exception as e:
        print(f"Error redeploying 2: {e}")

if __name__ == "__main__":
    redeploy_broken()
