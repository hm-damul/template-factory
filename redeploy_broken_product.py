from src.auto_heal_system import AutoHealSystem
from src.ledger_manager import LedgerManager
import logging

def redeploy_broken():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("Redeploy")
    
    lm = LedgerManager()
    ahs = AutoHealSystem(ledger_manager=lm)
    
    pid = "20260214-105333-global-merchant-crypto-checkou"
    logger.info(f"Redeploying product: {pid}")
    
    # Force redeploy
    ahs._redeploy_product(pid)
    
    # Also check the next one if any
    # 20260214-112651-aipassiveincomesystem
    pid2 = "20260214-112651-aipassiveincomesystem"
    logger.info(f"Redeploying product 2: {pid2}")
    ahs._redeploy_product(pid2)

if __name__ == "__main__":
    redeploy_broken()
