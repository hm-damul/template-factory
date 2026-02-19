import requests
import base64
import json

def test_wp_auth():
    wp_api_url = "https://dev-best-pick-global.pantheonsite.io/wp-json/wp/v2/posts"
    wp_token = "dev-best-pick-global:Qjdb rTlg hDT0 eJ1h kCGE gBMZ"
    
    headers = {"Content-Type": "application/json"}
    if ":" in wp_token:
        encoded_auth = base64.b64encode(wp_token.encode("utf-8")).decode("utf-8")
        headers["Authorization"] = f"Basic {encoded_auth}"
    else:
        headers["Authorization"] = f"Bearer {wp_token}"
    
    # Try to list posts first to check auth
    try:
        r = requests.get(wp_api_url, headers=headers, params={"per_page": 1}, timeout=10)
        print(f"Status Code: {r.status_code}")
        if r.status_code == 200:
            print("Auth successful!")
            posts = r.json()
            if posts:
                print(f"Latest post ID: {posts[0].get('id')}")
        else:
            print(f"Auth failed. Response: {r.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_wp_auth()
