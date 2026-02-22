import json
import os
import sys
import time
import requests
import base64
import re

def load_config():
    try:
        with open("data/secrets.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def main():
    secrets = load_config()
    wp_api_url = secrets.get("WP_API_URL", "")
    wp_token = secrets.get("WP_TOKEN", "")

    # If not found or empty, try to find in other files or use defaults
    if not wp_api_url:
        print("WP_API_URL not found in secrets.json, searching codebase...")
        pass

    if not wp_api_url or not wp_token:
        print("Missing WP credentials. Please ensure data/secrets.json has WP_API_URL and WP_TOKEN.")
        if not wp_api_url:
             wp_api_url = "https://dev-best-pick-global.pantheonsite.io/wp-json/wp/v2"
             print(f"Using fallback WP API URL: {wp_api_url}")

    # Clean WP API URL
    if wp_api_url.endswith("/posts"):
        wp_api_url = wp_api_url[:-6]
    if wp_api_url.endswith("/"):
        wp_api_url = wp_api_url[:-1]

    if not wp_api_url.endswith("/wp-json/wp/v2"):
        if "/wp-json" not in wp_api_url:
            wp_api_url = f"{wp_api_url}/wp-json/wp/v2"

    print(f"Using WP API URL: {wp_api_url}")

    # Clean token
    clean_token = wp_token.replace(" ", "")
    headers = {}
    if ":" in clean_token:
        encoded_auth = base64.b64encode(clean_token.encode("utf-8")).decode("utf-8")
        headers["Authorization"] = f"Basic {encoded_auth}"
    else:
        headers["Authorization"] = f"Bearer {clean_token}"
    headers["Content-Type"] = "application/json"

    target_product_id = "20260220-211248-digital-asset-bundle-2026-02-2"
    target_url = f"https://metapassiveincome-final.vercel.app/checkout/{target_product_id}"

    print(f"Target Product ID: {target_product_id}")
    print(f"Target URL: {target_url}")

    try:
        search_term = "Digital Asset Bundle"
        resp = requests.get(f"{wp_api_url}/posts?per_page=20&search={search_term}", headers=headers)

        if resp.status_code != 200:
            print(f"Error fetching posts: {resp.status_code} {resp.text}")
            sys.exit(1)

        posts = resp.json()
        print(f"Found {len(posts)} posts matching '{search_term}'")

        for post in posts:
            post_id = post["id"]
            title = post["title"]["rendered"]
            content = post["content"]["rendered"]
            print(f"Processing Post {post_id}: {title}")

            if target_product_id in content or "Digital Asset Bundle" in title:
                print(f"  -> Match found for target product.")

                new_content = content

                # Replace localhost links
                new_content = re.sub(r'http://127\.0\.0\.1:\d+/checkout/[^"\s]+', target_url, new_content)
                new_content = re.sub(r'http://localhost:\d+/checkout/[^"\s]+', target_url, new_content)

                if target_url not in new_content:
                    print("  -> Target URL not found in content, appending it.")
                    cta_html = f'''
                    <div style="margin-top: 20px; text-align: center;">
                        <a href="{target_url}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                            Get Instant Access Now
                        </a>
                    </div>
                    '''
                    new_content += cta_html

                if new_content != content:
                    print(f"  -> Updating post {post_id}...")
                    update_resp = requests.post(
                        f"{wp_api_url}/posts/{post_id}",
                        headers=headers,
                        json={"content": new_content}
                    )
                    if update_resp.status_code == 200:
                        print(f"  -> SUCCESS: Post {post_id} updated.")
                        print(f"  -> Verify at: {post['link']}")
                    else:
                        print(f"  -> FAILED: {update_resp.status_code} {update_resp.text}")
                else:
                    print("  -> No changes needed.")
            else:
                print("  -> Not a target product post.")

    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
