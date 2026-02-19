import json
import os
import requests
import base64
import sys
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from src.ledger_manager import LedgerManager
from src.config import Config
try:
    from promotion_dispatcher import _simple_markdown_to_html
except ImportError:
    # If running from root, this might be needed
    import sys
    sys.path.append(str(Path(__file__).parent))
    from promotion_dispatcher import _simple_markdown_to_html

def get_wp_credentials():
    try:
        with open("data/secrets.json", "r", encoding="utf-8") as f:
            secrets = json.load(f)
        url = secrets.get("WP_URL") or "https://dev-best-pick-global.pantheonsite.io/wp-json/wp/v2/posts"
        return url, secrets.get("WP_TOKEN")
    except Exception as e:
        print(f"Error reading secrets: {e}")
        return None, None

def get_auth_headers(token):
    if ":" in token:
        encoded_auth = base64.b64encode(token.encode("utf-8")).decode("utf-8")
        return {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/json",
        }
    else:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

def audit_and_fix():
    print(f"CWD: {os.getcwd()}")
    if not os.path.exists("data/secrets.json"):
        print("data/secrets.json NOT FOUND")
    
    wp_url, wp_token = get_wp_credentials()
    if not wp_url or not wp_token:
        print("CRITICAL: WP credentials not found in data/secrets.json")
        return

    # Normalize WP URL
    if "wp-json" not in wp_url:
        wp_url = wp_url.rstrip("/") + "/wp-json/wp/v2/posts"
    
    headers = get_auth_headers(wp_token)
    lm = LedgerManager(Config.DATABASE_URL)
    products = lm.get_all_products()
    
    print(f"Starting audit for {len(products)} products...")
    
    fixed_count = 0
    missing_post_count = 0
    
    for p in products:
        pid = p["id"]
        status = p["status"]
        meta = p.get("metadata", {})
        title = p["topic"]
        
        # We only care about products that should be live
        # if status not in ["PUBLISHED", "PROMOTED"]:
        #     continue
            
        deployment_url = meta.get("deployment_url")
        # if not deployment_url:
        #     print(f"[{pid}] SKIP: No deployment_url (Status: {status})")
        #     continue
            
        # Try to find the post
        post_id = meta.get("wp_post_id")
        posts = []
        
        # 1. Try by ID if we have it
        if post_id:
            try:
                r = requests.get(f"{wp_url}/{post_id}", headers=headers, timeout=10)
                if r.status_code == 200:
                    posts.append(r.json())
            except Exception as e:
                print(f"[{pid}] Error fetching post {post_id}: {e}")
        
        # 2. Search by title to find duplicates or missing
        try:
            # Clean title for search
            search_title = title.replace("&", "")
            search_url = f"{wp_url}?search={requests.utils.quote(search_title)}&per_page=5"
            r = requests.get(search_url, headers=headers, timeout=10)
            if r.status_code == 200:
                found_posts = r.json()
                for fp in found_posts:
                    # Check if already in list
                    if not any(p['id'] == fp['id'] for p in posts):
                        # Verify it's actually this product (fuzzy match title)
                        # WP search is fuzzy, so we should be careful.
                        # But for now, let's assume if title is unique enough.
                        posts.append(fp)
        except Exception as e:
            print(f"[{pid}] Error searching post: {e}")
        
        if not posts:
            if status in ["PUBLISHED", "PROMOTED"]:
                print(f"[{pid}] MISSING: Post not found in WP (Status: {status})")
                missing_post_count += 1
            continue
            
        print(f"[{pid}] Found {len(posts)} posts. Status: {status}")
        
        # Audit Each Post
        for post in posts:
            content = post.get("content", {}).get("rendered", "")
            needs_fix = False
            reasons = []
            
            # Check 1: Link to deployment
            if not deployment_url:
                 needs_fix = True
                 reasons.append("No deployment URL in ledger")
            else:
                clean_deploy_url = deployment_url.rstrip("/")
                if clean_deploy_url not in content:
                    needs_fix = True
                    reasons.append(f"Link mismatch (Expected {clean_deploy_url})")
                
                # Check 2: Verify Deployment URL reachable
                try:
                    r_head = requests.head(deployment_url, timeout=5)
                    if r_head.status_code >= 400:
                         print(f"[{pid}] WARNING: Deployment URL returns {r_head.status_code}")
                except:
                    pass

            # Check 3: Image
            if "<img" not in content:
                needs_fix = True
                reasons.append("Missing Image")
                
            if needs_fix:
                print(f"[{pid}] FIXING Post {post['id']}: {', '.join(reasons)}")
                
                # If we don't have deployment URL, we can't really fix the link...
                if not deployment_url:
                    print(f"[{pid}] Cannot fix Post {post['id']} - No deployment URL")
                    continue

                # Reconstruct HTML
                # Try to read the blog markdown from outputs
                blog_md_path = Path(f"outputs/{pid}/promotions/blog_longform.md")
                if blog_md_path.exists():
                    md_content = blog_md_path.read_text(encoding="utf-8")
                    # Replace placeholders
                    md_content = md_content.replace("(#)", f"({deployment_url})")
                    md_content = md_content.replace("(# \"", f"({deployment_url} \"")
                    md_content = md_content.replace("](#)", f"]({deployment_url})")
                    
                    # HTML conversion
                    new_html = _simple_markdown_to_html(md_content, title=title, target_url=deployment_url)
                    
                    # Update WP
                    try:
                        update_url = f"{wp_url}/{post['id']}"
                        update_payload = {
                            "content": new_html,
                            # "categories": post.get("categories") 
                        }
                        r = requests.post(update_url, headers=headers, json=update_payload, timeout=20)
                        if r.status_code == 200:
                            print(f"[{pid}] SUCCESS: Post {post['id']} updated.")
                            fixed_count += 1
                        else:
                            print(f"[{pid}] FAILED to update {post['id']}: {r.status_code}")
                    except Exception as e:
                        print(f"[{pid}] EXCEPTION updating {post['id']}: {e}")
                else:
                    print(f"[{pid}] ERROR: Cannot fix, source markdown not found at {blog_md_path}")
            else:
                print(f"[{pid}] OK: Post {post['id']} looks good.")

    print("==================================================")
    print(f"Audit Complete.")
    print(f"Fixed Posts: {fixed_count}")
    print(f"Missing Posts (Unfixed): {missing_post_count}")

if __name__ == "__main__":
    audit_and_fix()
