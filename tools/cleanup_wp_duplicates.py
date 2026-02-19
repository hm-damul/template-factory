import requests
import json
import os
import base64
from pathlib import Path
from collections import defaultdict

def load_secrets():
    secrets_path = Path("data/secrets.json")
    if secrets_path.exists():
        with open(secrets_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def cleanup_duplicates():
    secrets = load_secrets()
    wp_url = secrets.get("WP_URL") or "https://dev-best-pick-global.pantheonsite.io/wp-json/wp/v2/posts"
    wp_token = secrets.get("WP_TOKEN")
    
    if not wp_token:
        print("Error: WP_TOKEN not found in secrets.")
        return

    headers = {
        "Content-Type": "application/json",
    }
    if ":" in wp_token:
        encoded_auth = base64.b64encode(wp_token.encode("utf-8")).decode("utf-8")
        headers["Authorization"] = f"Basic {encoded_auth}"
    else:
        headers["Authorization"] = f"Bearer {wp_token}"

    print(f"Fetching posts from {wp_url}...")
    
    all_posts = []
    page = 1
    while True:
        r = requests.get(f"{wp_url}?per_page=100&page={page}", headers=headers)
        if r.status_code != 200:
            print(f"Error fetching page {page}: {r.status_code}")
            break
        
        data = r.json()
        if not data:
            break
            
        all_posts.extend(data)
        print(f"Fetched page {page} ({len(data)} posts)...")
        if len(data) < 100:
            break
        page += 1
        
    print(f"Total posts fetched: {len(all_posts)}")
    
    # Group by title
    posts_by_title = defaultdict(list)
    for p in all_posts:
        title = p["title"]["rendered"]
        posts_by_title[title].append(p)
        
    # Find duplicates
    duplicates_found = 0
    deleted_count = 0
    
    for title, posts in posts_by_title.items():
        if len(posts) > 1:
            print(f"\nFound {len(posts)} duplicates for: '{title}'")
            duplicates_found += 1
            
            # Sort by ID (usually implies creation order)
            posts.sort(key=lambda x: x["id"])
            
            # Keep the first one (oldest) or last one (newest)?
            # Usually keep the oldest to preserve links, or newest if content is updated.
            # Let's keep the NEWEST one as it might be the most "correct" one if previous ones failed.
            # actually, if we want to stop the loop, keeping the oldest is better for SEO (age).
            # But the user screenshot shows they are all recent.
            # Let's keep the OLDEST (first in list).
            
            keep = posts[0]
            to_delete = posts[1:]
            
            print(f"  Keeping ID: {keep['id']} (Date: {keep['date']})")
            
            for p in to_delete:
                print(f"  Deleting ID: {p['id']} (Date: {p['date']})...")
                del_url = f"{wp_url}/{p['id']}?force=true"
                r = requests.delete(del_url, headers=headers)
                if r.status_code in [200, 204]:
                    print("    Success.")
                    deleted_count += 1
                else:
                    print(f"    Failed: {r.status_code} - {r.text}")

    print(f"\nCleanup finished. Found {duplicates_found} duplicate sets. Deleted {deleted_count} posts.")

if __name__ == "__main__":
    cleanup_duplicates()
