
import logging
from src.payment_flow_verifier import PaymentFlowVerifier
import requests
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    product_id = "test-product-simulated"
    url = "http://localhost:8080"
    
    # We can't easily force simulated via PaymentFlowVerifier unless we modify it or the API allows query params overrides for POST?
    # api/main.py handle_start checks data.get('provider') for force_provider.
    
    # But PaymentFlowVerifier.verify_payment_flow sends:
    # payload = {
    #     "product_id": product_id,
    #     "amount": price,
    #     "currency": "usd",
    #     "email": "verification_bot@example.com"
    # }
    # It doesn't allow injecting 'provider': 'simulated'.
    
    # So we'll test manually here first to confirm API works.
    
    payload = {
        "product_id": product_id,
        "amount": 1.0,
        "currency": "usd",
        "provider": "simulated"
    }
    
    try:
        resp = requests.post(f"{url}/api/pay/start", json=payload)
        logger.info(f"Response: {resp.status_code}")
        logger.info(f"Body: {resp.json()}")
        
        if resp.status_code == 200:
            data = resp.json()
            if "order_id" in data:
                logger.info("Simulated payment created successfully.")
            else:
                logger.error("Missing order_id in simulated response.")
        else:
            logger.error(f"Failed: {resp.text}")
            
    except Exception as e:
        logger.error(f"Exception: {e}")

if __name__ == "__main__":
    main()
