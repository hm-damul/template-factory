import requests
import json
import sys

post_id = sys.argv[1] if len(sys.argv) > 1 else "671"
url = f"https://dev-best-pick-global.pantheonsite.io/wp-json/wp/v2/posts/{post_id}"
response = requests.get(url)

if response.status_code == 200:
    content = response.json()['content']['rendered']
    if "Share this Asset" in content:
        print(f"✅ Social sharing section found in post {post_id}")
        # Find the social sharing links
        if "twitter.com/intent/tweet" in content:
            print("  - Twitter link found")
        if "linkedin.com/sharing/share-offsite" in content:
            print("  - LinkedIn link found")
        if "t.me/share/url" in content:
            print("  - Telegram link found")
    else:
        print(f"❌ Social sharing section NOT found in post {post_id}")
else:
    print(f"Error: {response.status_code}")
