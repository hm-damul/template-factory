from src.auto_heal_system import AutoHealSystem
from src.ledger_manager import LedgerManager
import logging
import sys

def fix_broken_deployment():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    logger = logging.getLogger("FixDeployment")
    
    ahs = AutoHealSystem()
    target_pid = "20260214-105333-global-merchant-crypto-checkou"
    
    logger.info(f"Attempting to redeploy {target_pid}...")
    try:
        url = ahs._redeploy_product(target_pid)
        if url:
            logger.info(f"Redeployment successful: {url}")
        else:
            logger.error(f"Redeployment failed for {target_pid}")
    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    fix_broken_deployment()
