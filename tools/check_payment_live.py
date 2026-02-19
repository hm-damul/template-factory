import requests
import sys

def check_payment(url):
    try:
        print(f"Checking {url}...")
        response = requests.get(url, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Headers: {response.headers}")
        if response.status_code == 200:
            print("Response:", response.text[:200])
        else:
            print("Error Response:", response.text[:200])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    base_url = "https://meta-passive-income-20260215-212725-token-gated-cont-ri2dj9k54.vercel.app"
    endpoint = "/api/pay/start?product_id=20260215-212725-token-gated-content-revenue-au&price_amount=29&price_currency=usd"
    check_payment(base_url + endpoint)
