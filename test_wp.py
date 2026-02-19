import requests
import json

def check_wp_post(post_id):
    api_url = f"https://dev-best-pick-global.pantheonsite.io/wp-json/wp/v2/posts/{post_id}"
    try:
        r = requests.get(api_url, timeout=10)
        print(f"Status Code: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"Title: {data.get('title', {}).get('rendered')}")
            print(f"Link: {data.get('link')}")
            print(f"Status: {data.get('status')}")
        else:
            print(f"Response: {r.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_wp_post(626)
