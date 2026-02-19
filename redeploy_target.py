from src.auto_heal_system import AutoHealSystem
import logging
import sys

def redeploy_target():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    logger = logging.getLogger("RedeployTarget")
    
    ahs = AutoHealSystem()
    target_pid = "20260214-105333-global-merchant-crypto-checkou"
    
    logger.info(f"Redeploying {target_pid} with new vercel.json config...")
    try:
        # Force redeploy
        ahs._redeploy_product(target_pid)
        logger.info("Redeployment triggered.")
    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    redeploy_target()
