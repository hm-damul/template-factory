import requests
from bs4 import BeautifulSoup

def verify_dashboard():
    try:
        url = "http://127.0.0.1:8099"
        print(f"Fetching {url}...")
        r = requests.get(url, timeout=5)
        if r.status_code != 200:
            print(f"Failed to fetch dashboard: {r.status_code}")
            return

        soup = BeautifulSoup(r.text, 'html.parser')
        
        # 1. Count Orders
        # Find h2 with text "Orders (data/orders.json)"
        h2 = soup.find('h2', string=lambda t: t and "Orders (data/orders.json)" in t)
        if h2:
            orders_table = h2.find_next('table')
            if orders_table:
                rows = orders_table.find_all('tr')
                # Subtract header row
                count = len(rows) - 1
                print(f"Orders found in HTML: {count}")
                
                # Verify first row has product title
                if count > 0:
                    first_row = rows[1]
                    cols = first_row.find_all('td')
                    if len(cols) > 1:
                        product_col = cols[1]
                        print(f"First order product info: {product_col.get_text(strip=True)}")
            else:
                print("Orders table not found after h2!")
        else:
            print("Orders h2 header not found!")

        # 2. Check for redeployed products in product list
        # Find h2 with text "Products" or similar?
        # The code shows "System Health & Sales Summary" and then probably products table?
        # Actually line 491+ shows TEMPLATE...
        # Let's search for the product ID directly in the whole soup text
        text = soup.get_text()
        redeployed = [
            "20260214-133737-ai-powered-passive-income-syst",
            "20260214-130903-ai-trading-bot"
        ]
        for pid in redeployed:
            if pid in text:
                print(f"Product {pid} found in dashboard.")
            else:
                print(f"Product {pid} NOT found in dashboard.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify_dashboard()
