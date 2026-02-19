import requests
from bs4 import BeautifulSoup

try:
    response = requests.get("http://127.0.0.1:8099/")
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        badges = soup.find_all('span', class_=lambda x: x and 'badge' in x)
        print(f"Found {len(badges)} badges:")
        for badge in badges:
            print(f"- {badge.get_text().strip()} (Class: {badge['class']})")
    else:
        print(f"Failed to fetch dashboard: {response.status_code}")
except Exception as e:
    print(f"Error: {e}")
