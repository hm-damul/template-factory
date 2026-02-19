from src.auto_heal_system import AutoHealSystem
from src.ledger_manager import LedgerManager
from src.config import Config
import logging
import sys

def run_full_audit():
    # Configure root logger to output to stdout
    logging.basicConfig(
        level=logging.INFO, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("full_audit.log", encoding='utf-8')
        ]
    )
    
    logger = logging.getLogger("FullAudit")
    logger.info("Starting full system audit...")
    
    try:
        # Initialize AutoHealSystem
        ahs = AutoHealSystem()
        
        # Run full audit and heal process
        ahs.run_full_audit_and_heal()
        
        logger.info("Full system audit completed successfully.")
        
    except Exception as e:
        logger.error(f"Full system audit failed: {e}", exc_info=True)

if __name__ == "__main__":
    run_full_audit()
