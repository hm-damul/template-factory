import json
import requests
import base64
from pathlib import Path
import re

# Set paths
PROJECT_ROOT = Path("d:/auto/MetaPassiveIncome_FINAL")
DATA_DIR = PROJECT_ROOT / "data"
SECRETS_PATH = DATA_DIR / "secrets.json"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

def load_secrets():
    if SECRETS_PATH.exists():
        with open(SECRETS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def upload_image_standalone(file_path: Path, api_url: str, token: str) -> str:
    if not file_path.exists():
        return ""
    
    # WP Media Endpoint
    if "/posts" in api_url:
        media_url = api_url.replace("/posts", "/media")
    else:
        media_url = api_url.rstrip("/") + "/media"
        
    try:
        headers = {}
        if ":" in token:
            encoded_auth = base64.b64encode(token.encode("utf-8")).decode("utf-8")
            headers["Authorization"] = f"Basic {encoded_auth}"
        else:
            headers["Authorization"] = f"Bearer {token}"
        
        ext = file_path.suffix.lower()
        mime_type = "image/jpeg"
        if ext == ".png": mime_type = "image/png"
        elif ext == ".gif": mime_type = "image/gif"
        elif ext == ".webp": mime_type = "image/webp"
        elif ext == ".svg": mime_type = "image/svg+xml"

        headers["Content-Disposition"] = f'attachment; filename="{file_path.name}"'
        headers["Content-Type"] = mime_type
        
        with open(file_path, "rb") as img_file:
            print(f"Uploading {file_path.name}...")
            r = requests.post(media_url, headers=headers, data=img_file, timeout=60)
            
        if 200 <= r.status_code < 300:
            data = r.json()
            return data.get("source_url", "")
        else:
            print(f"Image upload failed: {r.status_code} - {r.text[:200]}")
            return ""
    except Exception as e:
        print(f"Image upload exception: {e}")
        return ""

def fix_posts():
    secrets = load_secrets()
    wp_url = secrets.get("WP_URL")
    if not wp_url:
        wp_url = "https://dev-best-pick-global.pantheonsite.io/wp-json/wp/v2/posts"
    if not wp_url.endswith("posts"):
         wp_url = wp_url.rstrip("/") + "/posts"
         
    wp_token = secrets.get("WP_TOKEN")
    
    if not wp_token:
        print("WP_TOKEN missing in secrets.json")
        return

    # Auth headers
    if ":" in wp_token:
        encoded_auth = base64.b64encode(wp_token.encode("utf-8")).decode("utf-8")
        headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/json",
        }
    else:
        headers = {
            "Authorization": f"Bearer {wp_token}",
            "Content-Type": "application/json",
        }

    # Iterate products
    if not OUTPUTS_DIR.exists():
        print("Outputs dir not found")
        return

    for product_dir in OUTPUTS_DIR.iterdir():
        if not product_dir.is_dir():
            continue
            
        manifest_path = product_dir / "manifest.json"
        if not manifest_path.exists():
            continue
            
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            title = manifest.get("title")
            product_id = manifest.get("id", product_dir.name)
            
            if not title:
                continue
                
            print(f"Checking post for: {title}")
            
            # Find post by title
            search_url = f"{wp_url}?search={requests.utils.quote(title)}&per_page=5"
            r = requests.get(search_url, headers=headers, timeout=10)
            
            if r.status_code == 200:
                posts = r.json()
                if not posts:
                    print("  - Post not found")
                    continue
                
                # Check for local cover
                cover_path = product_dir / "assets" / "cover.jpg"
                uploaded_cover_url = ""
                
                if cover_path.exists():
                    print(f"  - Found local cover: {cover_path}")
                    # Upload once per product
                    uploaded_cover_url = upload_image_standalone(cover_path, wp_url, wp_token)
                else:
                    print("  - No local cover found")

                if not uploaded_cover_url:
                    print("  - Skipping update (no cover uploaded)")
                    continue

                for post in posts:
                    post_id = post["id"]
                    print(f"  - Processing post {post_id}...")
                    
                    # Get content
                    r_detail = requests.get(f"{wp_url}/{post_id}?context=edit", headers=headers, timeout=10)
                    if r_detail.status_code == 200:
                        content_raw = r_detail.json()["content"]["raw"]
                        new_content = content_raw
                        changed = False
                        
                        # Fix malformed src attributes (src="url "title"")
                        # Regex to find src="url "title""
                        # We look for src="... "..."
                        malformed_pattern = re.compile(r'src="([^"]+)\s+"[^"]+""')
                        if malformed_pattern.search(new_content):
                            new_content = malformed_pattern.sub(r'src="\1"', new_content)
                            changed = True
                            print("  - Fixed malformed src attributes")

                        # Replace Unsplash URLs
                        if "unsplash.com" in new_content:
                            # Replace generic Unsplash links
                            new_content = re.sub(r'https://images\.unsplash\.com/[^"\')\s]+', uploaded_cover_url, new_content)
                            changed = True
                            print("  - Replaced Unsplash URLs")
                            
                        # Replace assets/ paths
                        if "assets/" in new_content:
                            pattern = re.compile(r'src=["\'](assets/[^"\']+)["\']')
                            matches = set(pattern.findall(new_content))
                            for relative_path in matches:
                                new_content = new_content.replace(relative_path, uploaded_cover_url)
                                changed = True
                                print(f"  - Replaced {relative_path}")
                        
                        # Also replace markdown image syntax if present (less likely in raw html but possible)
                        if "](assets/" in new_content:
                             new_content = new_content.replace("](assets/cover.jpg)", f"]({uploaded_cover_url})")
                             changed = True

                        if changed:
                            # Update post
                            r_update = requests.post(f"{wp_url}/{post_id}", headers=headers, json={"content": new_content}, timeout=20)
                            if r_update.status_code == 200:
                                print(f"  - Updated post {post_id}")
                            else:
                                print(f"  - Failed to update post {post_id}: {r_update.status_code}")
                        else:
                            print("  - No images needed replacement")
                    else:
                        print(f"  - Failed to get content for {post_id}")

            else:
                print(f"  - Search failed: {r.status_code}")
                
        except Exception as e:
            print(f"Error processing {product_dir.name}: {e}")

if __name__ == "__main__":
    fix_posts()
