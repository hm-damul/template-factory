
import logging
from src.payment_flow_verifier import PaymentFlowVerifier
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    product_id = "test-product-123"
    url = "http://localhost:8080"
    
    logger.info(f"Verifying payment flow for {product_id} at {url}")
    
    verifier = PaymentFlowVerifier()
    is_verified, msg, details = verifier.verify_payment_flow(product_id, url, 1.0)
    
    logger.info(f"Result: {is_verified}")
    logger.info(f"Message: {msg}")
    logger.info(f"Details: {details}")

if __name__ == "__main__":
    main()
