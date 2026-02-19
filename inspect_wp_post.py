import requests
import json
import base64
from pathlib import Path

def inspect_post(post_id):
    with open("d:/auto/MetaPassiveIncome_FINAL/data/secrets.json", "r", encoding="utf-8") as f:
        secrets = json.load(f)
    wp_url = secrets.get("WP_URL")
    if not wp_url: wp_url = "https://dev-best-pick-global.pantheonsite.io/wp-json/wp/v2/posts"
    if not wp_url.endswith("posts"):
         wp_url = wp_url.rstrip("/") + "/posts"
         
    wp_token = secrets.get("WP_TOKEN")
    
    if ":" in wp_token:
        encoded_auth = base64.b64encode(wp_token.encode("utf-8")).decode("utf-8")
        headers = {'Authorization': 'Basic ' + encoded_auth}
    else:
        headers = {'Authorization': 'Bearer ' + wp_token}
    
    r = requests.get(f"{wp_url}/{post_id}?context=edit", headers=headers)
    if r.status_code == 200:
        data = r.json()
        print(f"Title: {data['title']['raw']}")
        print("Content Raw Snippet:")
        # Find img tag
        import re
        match = re.search(r'<img[^>]+>', data['content']['raw'])
        if match:
            print(f"Found Image Tag: {match.group(0)}")
        else:
            print("No image tag found in raw content")
        print(data['content']['raw'][:200])
    else:
        print(f"Error: {r.status_code}")

if __name__ == "__main__":
    inspect_post(686)
