import requests
import json
from pathlib import Path

def get_wp_categories():
    secrets_path = Path('data/secrets.json')
    if not secrets_path.exists():
        print("secrets.json not found")
        return
    
    secrets = json.loads(secrets_path.read_text(encoding='utf-8'))
    token = secrets.get('WP_TOKEN')
    # Use the same base URL as in promotion_dispatcher.py but for categories
    api_url = "https://dev-best-pick-global.pantheonsite.io/wp-json/wp/v2/categories"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        r = requests.get(api_url, headers=headers, timeout=20)
        print(f"Status: {r.status_code}")
        print(f"Response: {r.text[:500]}")
        r.raise_for_status()
        categories = r.json()
        if not categories:
            print("No categories found")
        for cat in categories:
            print(f"Category ID: {cat['id']}, Name: {cat['name']}, Slug: {cat['slug']}")
            
        print("\n--- Also checking Tags ---\n")
        tag_url = "https://dev-best-pick-global.pantheonsite.io/wp-json/wp/v2/tags"
        r2 = requests.get(tag_url, headers=headers, timeout=20)
        r2.raise_for_status()
        tags = r2.json()
        for tag in tags:
            print(f"Tag ID: {tag['id']}, Name: {tag['name']}, Slug: {tag['slug']}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_wp_categories()
