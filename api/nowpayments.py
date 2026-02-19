import requests
import json
import os

try:
    from . import app_secrets as secrets
except ImportError:
    import app_secrets as secrets

# Clean the key if necessary
API_KEY = secrets.NOWPAYMENTS_API_KEY.replace("-widgetOnLoad", "").strip()
BASE_URL = secrets.NOWPAYMENTS_BASE_URL

def _headers():
    return {
        "x-api-key": API_KEY,
        "Content-Type": "application/json"
    }

def create_payment(order_id, product_id, amount, currency="usd"):
    url = f"{BASE_URL}/v1/payment"
    payload = {
        "price_amount": float(amount),
        "price_currency": currency.lower(),
        "pay_currency": "usdttrc20", # Default to USDT-TRC20 as per secrets.json
        "order_id": order_id,
        "order_description": f"Product: {product_id}",
        "ipn_callback_url": "https://metapassiveincome-final.vercel.app/api/pay/ipn" # Optional
    }
    
    try:
        response = requests.post(url, headers=_headers(), json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"NOWPayments Error: {e}")
        # Fallback for demo if API fails (so system doesn't break completely)
        # BUT user asked for "Normal Operation", so we should try to be real.
        # If real fails, we return error.
        return None

def get_payment_status(payment_id):
    url = f"{BASE_URL}/v1/payment/{payment_id}"
    try:
        response = requests.get(url, headers=_headers(), timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"NOWPayments Status Error: {e}")
        return None
