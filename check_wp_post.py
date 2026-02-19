import json
import os
import sys
import requests
import re
sys.path.append(os.getcwd())

def check_wp_post():
    try:
        with open(r"d:\auto\MetaPassiveIncome_FINAL\data\secrets.json", "r", encoding="utf-8") as f:
            secrets = json.load(f)
        url = secrets.get("WP_URL")
        if not url:
            url = "https://dev-best-pick-global.pantheonsite.io/wp-json/wp/v2/posts"
        if not url.endswith("posts"):
             url = url.rstrip("/") + "/posts"
             
        url = url + '?per_page=5'
        token = secrets.get("WP_TOKEN")
    except Exception as e:
        print(f"Failed to load secrets: {e}")
        return

    headers = {'Authorization': 'Bearer ' + token}
    try:
        r = requests.get(url, headers=headers)
        posts = r.json()
        if posts:
            for post in posts:
                print(f"Title: {post['title']['rendered']}")
                content = post['content']['rendered']
                # Find img tags
                imgs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', content)
                print(f"Images found: {len(imgs)}")
                for img in imgs:
                    print(f" - {img}")
                print("-" * 20)
        else:
            print("No posts found")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_wp_post()
