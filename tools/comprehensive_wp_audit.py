import json
import os
import sys
import re
import requests
import base64
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ledger_manager import LedgerManager
from src.config import Config

# --- Helper Functions ---

def get_wp_credentials():
    try:
        with open("data/secrets.json", "r", encoding="utf-8") as f:
            secrets = json.load(f)
        url = secrets.get("WP_URL") or "https://dev-best-pick-global.pantheonsite.io/wp-json/wp/v2/posts"
        token = secrets.get("WP_TOKEN")
        return url, token
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

def _humanize_title(slug: str) -> str:
    """Converts a slug-like string to a human-readable title."""
    if not slug:
        return ""
    if " " in slug and not slug.islower():
        return slug
    title = slug.replace("-", " ").replace("_", " ")
    return title.title()

def _simple_markdown_to_html(md: str, title: str = "", target_url: str = "", price: str = "29.00") -> str:
    lines = md.splitlines()
    out = []
    
    out.append("""
<style>
    .wp-promo-container { font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; }
    .wp-promo-header { text-align: center; margin-bottom: 40px; padding: 20px; background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); border-radius: 16px; }
    .wp-promo-header h1 { color: #1e293b; font-size: 2.5rem; margin-bottom: 16px; font-weight: 800; }
    .wp-promo-header h3 { color: #64748b; font-size: 1.25rem; font-weight: 400; }
    .wp-promo-image { width: 100%; border-radius: 12px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.1); margin: 30px 0; transition: transform 0.3s ease; }
    .wp-promo-image:hover { transform: translateY(-5px); }
    .wp-promo-cta { display: block; background: #2563eb; color: #ffffff !important; text-align: center; padding: 18px 32px; border-radius: 12px; font-weight: 700; font-size: 1.25rem; text-decoration: none !important; margin: 40px 0; box-shadow: 0 4px 14px 0 rgba(37, 99, 235, 0.39); }
    .wp-promo-cta:hover { background: #1d4ed8; transform: scale(1.02); }
    .wp-promo-section { margin: 40px 0; padding: 20px; border-left: 4px solid #3b82f6; background: #f0f9ff; border-radius: 0 12px 12px 0; }
    .wp-promo-section h2 { color: #1e3a8a; margin-top: 0; }
    .wp-promo-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 30px 0; }
    @media (max-width: 600px) { .wp-promo-grid { grid-template-columns: 1fr; } }
    .wp-promo-card { padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px; background: white; }
    .wp-promo-highlight { background: #eff6ff !important; font-weight: 600; color: #2563eb !important; }
</style>
<div class="wp-promo-container">
""")

    in_list = False
    
    for ln in lines:
        ln = ln.rstrip()
        
        if ln.startswith("# "):
            out.append(f'<div class="wp-promo-header"><h1>{ln[2:].strip()}</h1>')
        elif ln.startswith("### "):
            out.append(f"<h3>{ln[4:].strip()}</h3></div>")
        elif ln.startswith("## "):
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f'<div class="wp-promo-section"><h2>{ln[3:].strip()}</h2>')
            
        elif ln.startswith("![") and "](" in ln and ln.endswith(")"):
            try:
                alt = ln[2 : ln.find("]")]
                url_content = ln[ln.find("(") + 1 : -1]
                url = url_content.split(' "')[0] if ' "' in url_content else url_content
                out.append(f'<img src="{url}" alt="{alt}" class="wp-promo-image" />')
            except:
                out.append(f"<p>{ln}</p>")

        elif ln.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            content = ln[2:].strip()
            content = re.sub(r'\*\*([^\*]+)\*\*', r'<strong>\1</strong>', content)
            content = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', content)
            out.append(f"<li>{content}</li>")
            
        else:
            cta_match = re.match(r'^\[([^\]]+)\]\(([^\)]+)\)$', ln.strip())
            if cta_match:
                text = cta_match.group(1)
                url = cta_match.group(2)
                if any(k in text.upper() for k in ["DOWNLOAD", "ACCESS", "GET", "BUY", "BUNDLE", "NOW", "CHECKOUT"]):
                    out.append(f'<a href="{url}" class="wp-promo-cta">{text}</a>')
                    continue
            
            ln = re.sub(r'\*\*([^\*]+)\*\*', r'<strong>\1</strong>', ln)
            
            if not ln.startswith("<img"):
                ln = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2" style="color: #2563eb; text-decoration: underline; font-weight: 600;">\1</a>', ln)
            
            if ln.strip() == "":
                if in_list:
                    out.append("</ul>")
                    in_list = False
                out.append("<br/>")
            elif ln.startswith("---"):
                if in_list:
                    out.append("</ul>")
                    in_list = False
                out.append('<hr style="border: 0; height: 1px; background: #e2e8f0; margin: 40px 0;" />')
            else:
                out.append(f"<p>{ln}</p>")
            
    if in_list:
        out.append("</ul>")
        
    out.append("</div>")
    return "\n".join(out)

def get_all_posts(wp_url, headers):
    all_posts = []
    page = 1
    while True:
        r = requests.get(f"{wp_url}?per_page=20&page={page}", headers=headers)
        if r.status_code != 200:
            break
        data = r.json()
        if not data:
            break
        all_posts.extend(data)
        if len(data) < 20:
            break
        page += 1
    return all_posts

# --- Main Audit Logic ---

def run_audit():
    print("Starting Comprehensive WP Audit...")
    
    wp_url, wp_token = get_wp_credentials()
    if not wp_url or not wp_token:
        print("Error: Missing WP credentials.")
        return
        
    headers = get_auth_headers(wp_token)
    
    lm = LedgerManager(Config.DATABASE_URL)
    products = lm.get_all_products()
    print(f"Loaded {len(products)} products from ledger.")
    
    prod_map_by_title = {}
    prod_map_by_url = {}
    for p in products:
        meta = p.get("metadata") or {}
        title = meta.get("title") or p.get("topic")
        url = meta.get("deployment_url")
        
        if title:
            key = title.lower().strip()
            prod_map_by_title[key] = p
        if url:
            key = url.strip().rstrip("/")
            prod_map_by_url[key] = p
            
    print("Fetching all WP posts...")
    posts = get_all_posts(wp_url, headers)
    print(f"Loaded {len(posts)} posts from WordPress.")
    
    fixed_count = 0
    matched_product_ids = set()
    
    for post in posts:
        post_id = post["id"]
        post_title = post["title"]["rendered"]
        post_content = post["content"]["rendered"]
        
        print(f"\nAudit Post [{post_id}]: {post_title}")
        
        needs_update = False
        update_data = {}
        
        if "-" in post_title and " " not in post_title:
            new_title = _humanize_title(post_title)
            if new_title != post_title:
                print(f"  [TITLE FIX] {post_title} -> {new_title}")
                update_data["title"] = new_title
                needs_update = True
                
        matched_product = None
        for url, p in prod_map_by_url.items():
            if url in post_content:
                matched_product = p
                print(f"  [MATCH] Found product by URL: {p['id']}")
                break
                
        if not matched_product:
            norm_title = post_title.lower().replace("-", " ").strip()
            if norm_title in prod_map_by_title:
                matched_product = prod_map_by_title[norm_title]
                print(f"  [MATCH] Found product by exact title: {matched_product['id']}")
            else:
                for k, p in prod_map_by_title.items():
                    if k in norm_title or norm_title in k:
                        matched_product = p
                        print(f"  [MATCH] Found product by fuzzy title: {p['id']}")
                        break
        
        if matched_product:
            matched_product_ids.add(matched_product['id'])
        
        has_broken_md = bool(re.search(r'\[([^\]]+)\]\(([^\)]+)\)', post_content))
        if has_broken_md:
            print("  [CONTENT] Found broken Markdown links.")
            
        if matched_product:
            pid = matched_product["id"]
            blog_path = Path(f"outputs/{pid}/promotions/blog_longform.md")
            if not blog_path.exists():
                blog_path = Path(f"outputs/{pid}/promotions/blog_post.md")
                
            if blog_path.exists():
                md_content = blog_path.read_text(encoding="utf-8")
                deploy_url = matched_product.get("metadata", {}).get("deployment_url", "")
                if deploy_url:
                    md_content = md_content.replace("(#)", f"({deploy_url})")
                    md_content = md_content.replace("](#)", f"]({deploy_url})")
                    md_content = md_content.replace("(# \"", f"({deploy_url} \"")
                
                new_html = _simple_markdown_to_html(
                    md_content, 
                    title=update_data.get("title", post_title),
                    target_url=deploy_url
                )
                
                if has_broken_md or abs(len(new_html) - len(post_content)) > 50:
                    print(f"  [RE-RENDER] Regenerating HTML from source (Length diff: {len(new_html) - len(post_content)})")
                    update_data["content"] = new_html
                    needs_update = True
            else:
                print(f"  [WARNING] Source markdown not found for {pid}.")
        else:
            if has_broken_md:
                print("  [IN-PLACE FIX] Attempting regex fix on existing content...")
                fixed_content = post_content
                fixed_content = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2" style="color: #2563eb; font-weight: 600;">\1</a>', fixed_content)
                fixed_content = re.sub(r'<p>\[([^\]]+)\]\(([^\)]+)\)</p>', r'<a href="\2" class="wp-promo-cta">\1</a>', fixed_content)
                
                if fixed_content != post_content:
                    update_data["content"] = fixed_content
                    needs_update = True

        if needs_update:
            print(f"  [UPDATE] Sending update to WordPress...")
            try:
                r = requests.post(f"{wp_url}/{post_id}", headers=headers, json=update_data, timeout=20)
                if r.status_code == 200:
                    print(f"  [SUCCESS] Post {post_id} updated.")
                    fixed_count += 1
                else:
                    print(f"  [FAILED] {r.status_code} - {r.text[:100]}")
            except Exception as e:
                print(f"  [ERROR] {e}")
        else:
            print("  [OK] No changes needed.")

    print(f"\nAudit Complete. Fixed {fixed_count} posts.")
    
    # --- Check 4: Restore Missing Posts ---
    print("\nChecking for Missing Products (PROMOTED/PUBLISHED but no Post found)...")
    restored_count = 0
    
    for p in products:
        pid = p["id"]
        status = p["status"]
        if status in ["PUBLISHED", "PROMOTED", "QA2_PASSED"] and pid not in matched_product_ids:
            print(f"\n[MISSING POST] Product {pid} (Status: {status})")
            
            # Try to restore
            blog_path = Path(f"outputs/{pid}/promotions/blog_longform.md")
            if not blog_path.exists():
                blog_path = Path(f"outputs/{pid}/promotions/blog_post.md")
            
            if blog_path.exists():
                print(f"  Found promotion content at {blog_path}")
                md_content = blog_path.read_text(encoding="utf-8")
                
                meta = p.get("metadata") or {}
                deploy_url = meta.get("deployment_url", "")
                title = meta.get("title") or p.get("topic")
                title = _humanize_title(title)
                
                if deploy_url:
                    md_content = md_content.replace("(#)", f"({deploy_url})")
                    md_content = md_content.replace("](#)", f"]({deploy_url})")
                    md_content = md_content.replace("(# \"", f"({deploy_url} \"")
                
                html_content = _simple_markdown_to_html(md_content, title=title, target_url=deploy_url)
                
                # Create Post
                payload = {
                    "title": title,
                    "content": html_content,
                    "status": "publish",
                    "categories": [1] # Default
                }
                
                try:
                    print(f"  Creating new WP post for {pid}...")
                    r = requests.post(wp_url, headers=headers, json=payload, timeout=20)
                    if r.status_code == 201:
                        new_post = r.json()
                        new_post_id = new_post["id"]
                        print(f"  [SUCCESS] Created Post {new_post_id}")
                        
                        # Update Ledger
                        meta["wp_post_id"] = new_post_id
                        lm.update_product_status(pid, "PROMOTED", metadata=meta)
                        restored_count += 1
                    else:
                        print(f"  [FAILED] {r.status_code} - {r.text[:100]}")
                except Exception as e:
                    print(f"  [ERROR] {e}")
            else:
                print(f"  [SKIPPED] No promotion content found for {pid}")

    print(f"\nRestored {restored_count} missing posts.")

if __name__ == "__main__":
    run_audit()
