import requests
import logging
import json
from typing import Dict, Any, Tuple

logger = logging.getLogger("PaymentFlowVerifier")

class PaymentFlowVerifier:
    def __init__(self):
        pass

    def verify_payment_flow(self, product_id: str, live_url: str, price: float = 1.0, provider: str = None) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Verifies the payment flow for a deployed product.
        
        Args:
            product_id: The ID of the product.
            live_url: The base URL of the deployed product (e.g., https://my-app.vercel.app).
            price: The price amount to simulate.
            provider: Optional provider to force (e.g. 'simulated').
            
        Returns:
            Tuple containing:
            - success (bool): True if verification passed.
            - message (str): Error message or success details.
            - details (dict): Detailed response data.
        """
        if not live_url:
            return False, "Live URL is empty", {}

        # Construct API endpoint
        api_url = f"{live_url.rstrip('/')}/api/pay/start"
        
        payload = {
            "product_id": product_id,
            "amount": price,
            "currency": "usd",
            "email": "verification_bot@example.com"
        }
        if provider:
            payload["provider"] = provider

        
        logger.info(f"Verifying payment flow for {product_id} at {api_url}")
        
        try:
            # 1. Check if the endpoint exists (OPTIONS/GET check) or just go straight to POST
            # Let's try POST directly as that's what the button does
            resp = requests.post(api_url, json=payload, timeout=30)
            
            if resp.status_code != 200:
                return False, f"API returned status code {resp.status_code}", {"status_code": resp.status_code, "text": resp.text}
            
            data = resp.json()
            
            # 2. Validate Response Structure
            if "payment_id" not in data:
                return False, "Missing 'payment_id' in response", data
            
            if "invoice_url" not in data and "payment_url" not in data:
                return False, "Missing 'invoice_url' or 'payment_url' in response", data
                
            invoice_url = data.get("invoice_url") or data.get("payment_url")
            
            # 3. Verify Invoice URL Reachability (Optional but recommended)
            if invoice_url:
                try:
                    inv_resp = requests.get(invoice_url, timeout=10)
                    if inv_resp.status_code >= 400:
                         return False, f"Invoice URL returned {inv_resp.status_code}", {"invoice_url": invoice_url}
                except Exception as e:
                    logger.warning(f"Failed to reach invoice URL: {e}")
                    # We don't fail strictly here as it might be a network issue, but it's suspicious
            
            return True, "Payment flow verified successfully", data
            
        except requests.exceptions.Timeout:
            return False, "Request timed out", {}
        except requests.exceptions.ConnectionError:
            return False, "Connection failed", {}
        except Exception as e:
            return False, f"Exception during verification: {str(e)}", {}
