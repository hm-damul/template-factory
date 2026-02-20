import requests
import json
import os
import random
import time

try:
    from . import app_secrets as secrets
except ImportError:
    import app_secrets as secrets

# Clean the key if necessary
API_KEY = secrets.NOWPAYMENTS_API_KEY.replace("-widgetOnLoad", "").strip()
BASE_URL = secrets.NOWPAYMENTS_BASE_URL

# Simulation Mode: Auto-detect if key is invalid format or explicit env var
SIMULATION_MODE = os.getenv("PAYMENT_SIMULATION", "true").lower() == "true"
if "ww-" in API_KEY or "widget" in API_KEY or len(API_KEY) < 20:
    SIMULATION_MODE = True

if SIMULATION_MODE:
    print("WARNING: NOWPayments running in SIMULATION MODE (Mock Payments)")

def _headers():
    return {
        "x-api-key": API_KEY,
        "Content-Type": "application/json"
    }

def create_payment(order_id, product_id, amount, currency="usd"):
    if SIMULATION_MODE:
        print(f"[SIMULATION] Creating payment for {product_id} (${amount})")
        return {
            "payment_id": f"sim_pay_{int(time.time())}_{random.randint(1000,9999)}",
            "payment_status": "waiting",
            "pay_address": "T_SIMULATED_USDT_ADDRESS_DO_NOT_SEND",
            "price_amount": float(amount),
            "price_currency": currency,
            "pay_amount": float(amount), # Simplified 1:1 for sim
            "pay_currency": "usdttrc20",
            "order_id": order_id,
            "created_at": "2026-02-20T12:00:00.000Z"
        }

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
        # If real fails, we return error.
        return None

def get_payment_status(payment_id):
    if SIMULATION_MODE and str(payment_id).startswith("sim_pay_"):
        print(f"[SIMULATION] Checking status for {payment_id}")
        # Always return finished for demo purposes to allow download
        return {
            "payment_id": payment_id,
            "payment_status": "finished",
            "pay_address": "T_SIMULATED_USDT_ADDRESS_DO_NOT_SEND",
            "price_amount": 19.90,
            "pay_amount": 19.90,
            "pay_currency": "usdttrc20",
            "order_id": "sim_order",
            "created_at": "2026-02-20T12:00:00.000Z"
        }

    url = f"{BASE_URL}/v1/payment/{payment_id}"
    try:
        response = requests.get(url, headers=_headers(), timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"NOWPayments Status Error: {e}")
        return None
