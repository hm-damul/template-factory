from src.auto_heal_system import AutoHealSystem
from src.ledger_manager import LedgerManager
import logging
import sys

def redeploy_remaining():
    # Configure logging to stdout
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    logger = logging.getLogger("RedeployRemaining")
    
    ahs = AutoHealSystem()
    
    # List of products identified with issues (403 or broken links)
    target_products = [
        "20260214-133737-ai-powered-passive-income-syst",
        "20260214-130903-ai-trading-bot"
    ]
    
    for pid in target_products:
        logger.info(f"Starting redeployment for product: {pid}")
        try:
            url = ahs._redeploy_product(pid)
            if url:
                logger.info(f"Successfully redeployed {pid} to {url}")
            else:
                logger.error(f"Failed to redeploy {pid}")
        except Exception as e:
            logger.error(f"Exception during redeployment of {pid}: {e}")

if __name__ == "__main__":
    redeploy_remaining()
