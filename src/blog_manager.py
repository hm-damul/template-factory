import os
import json
import requests
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

# Google Blogger API
try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
except ImportError:
    Credentials = None
    build = None

# Optional: OAuth for Tumblr
try:
    from requests_oauthlib import OAuth1
except ImportError:
    OAuth1 = None

class BlogManager:
    """
    Manages blog expansion to platforms like Medium, Tumblr, and GitHub Pages.
    Ensures policy compliance by setting canonical URLs to the original source.
    """
    
    MEDIUM_API_URL = "https://api.medium.com/v1"
    TUMBLR_API_URL = "https://api.tumblr.com/v2"
    
    def __init__(self, medium_token: Optional[str] = None, tumblr_creds: Optional[Dict] = None, github_creds: Optional[Dict] = None, blogger_creds: Optional[Dict] = None):
        self.medium_token = medium_token
        self.tumblr_creds = tumblr_creds
        self.github_creds = github_creds
        self.blogger_creds = blogger_creds
        
        self.medium_user_id = None
        
        if self.medium_token:
            self._fetch_medium_user_id()

    def _fetch_medium_user_id(self):
        """
        Fetches the authenticated user's ID from Medium.
        """
        headers = {
            "Authorization": f"Bearer {self.medium_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Charset": "utf-8"
        }
        try:
            response = requests.get(f"{self.MEDIUM_API_URL}/me", headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.medium_user_id = data['data']['id']
                print(f"✅ [BlogManager] Connected to Medium as {data['data']['username']}")
            else:
                print(f"❌ [BlogManager] Failed to authenticate Medium: {response.text}")
        except Exception as e:
            print(f"❌ [BlogManager] Error connecting to Medium: {e}")

    def publish_medium(self, title: str, content: str, tags: list, canonical_url: str = None) -> Optional[str]:
        """
        Publishes a post to Medium. Returns the URL if successful, None otherwise.
        """
        if not self.medium_token or not self.medium_user_id:
            print("⚠️ [BlogManager] Medium token missing or invalid. Saving draft locally.")
            self._save_local_draft(title, content, tags, "medium")
            return None

        headers = {
            "Authorization": f"Bearer {self.medium_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Charset": "utf-8"
        }

        payload = {
            "title": title,
            "contentFormat": "markdown",
            "content": content,
            "tags": tags[:5],  # Medium allows max 5 tags
            "publishStatus": "public",  # Changed to public for automated promotion (Canonical URL ensures compliance)
            "canonicalUrl": canonical_url
        }

        try:
            url = f"{self.MEDIUM_API_URL}/users/{self.medium_user_id}/posts"
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 201:
                data = response.json()
                post_url = data['data']['url']
                print(f"✅ [BlogManager] Published to Medium: {post_url}")
                return post_url
            else:
                print(f"❌ [BlogManager] Failed to publish to Medium: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ [BlogManager] Error publishing to Medium: {e}")
            return None

    def publish_tumblr(self, blog_identifier: str, title: str, content: str, tags: list, source_url: str = None) -> Optional[str]:
        """
        Publishes a post to Tumblr. Returns the Post URL if successful, None otherwise.
        Requires: consumer_key, consumer_secret, oauth_token, oauth_token_secret in tumblr_creds
        """
        if not self.tumblr_creds or not OAuth1:
            print("⚠️ [BlogManager] Tumblr credentials missing or OAuth1 not installed.")
            self._save_local_draft(title, content, tags, "tumblr")
            return None

        required_keys = ["consumer_key", "consumer_secret", "oauth_token", "oauth_token_secret"]
        if not all(k in self.tumblr_creds for k in required_keys):
             print("⚠️ [BlogManager] Incomplete Tumblr credentials.")
             return None

        try:
            auth = OAuth1(
                self.tumblr_creds["consumer_key"],
                self.tumblr_creds["consumer_secret"],
                self.tumblr_creds["oauth_token"],
                self.tumblr_creds["oauth_token_secret"]
            )
            
            url = f"{self.TUMBLR_API_URL}/blog/{blog_identifier}/post"
            
            # Use HTML format for better compatibility with Markdown-converted HTML
            # Or just send as text.
            payload = {
                "type": "text",
                "title": title,
                "body": content, 
                "tags": ",".join(tags),
                "source_url": source_url,
                "format": "markdown" # Tumblr supports markdown
            }
            
            response = requests.post(url, auth=auth, data=payload, timeout=30)
            
            if response.status_code in [201, 200]:
                data = response.json()
                post_id = data['response']['id']
                # Construct URL (Tumblr API doesn't always return the full URL)
                post_url = f"https://{blog_identifier}.tumblr.com/post/{post_id}"
                print(f"✅ [BlogManager] Published to Tumblr: {post_url}")
                return post_url
            else:
                print(f"❌ [BlogManager] Failed to publish to Tumblr: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ [BlogManager] Error publishing to Tumblr: {e}")
            return None

    def publish_blogger(self, blog_id: str, title: str, content: str, tags: list) -> Optional[str]:
        """
        Publishes a post to Blogger (Google Blogspot).
        Requires: client_id, client_secret, refresh_token in blogger_creds
        """
        if not self.blogger_creds or not Credentials or not build:
            print("⚠️ [BlogManager] Blogger credentials missing or Google API not installed.")
            self._save_local_draft(title, content, tags, "blogger")
            return None

        required_keys = ["client_id", "client_secret", "refresh_token"]
        if not all(k in self.blogger_creds for k in required_keys):
             print("⚠️ [BlogManager] Incomplete Blogger credentials.")
             return None

        try:
            creds = Credentials(
                token=None,
                refresh_token=self.blogger_creds.get("refresh_token"),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.blogger_creds.get("client_id"),
                client_secret=self.blogger_creds.get("client_secret")
            )
            
            service = build("blogger", "v3", credentials=creds)
            
            body = {
                "kind": "blogger#post",
                "blog": {"id": blog_id},
                "title": title,
                "content": content,
                "labels": tags
            }
            
            posts = service.posts()
            result = posts.insert(blogId=blog_id, body=body).execute()
            
            url = result.get("url")
            print(f"✅ [BlogManager] Published to Blogger: {url}")
            return url
            
        except Exception as e:
            print(f"❌ [BlogManager] Error publishing to Blogger: {e}")
            return None

    def publish_github_pages(self, repo_url: str, title: str, content: str, filename: str) -> Optional[str]:
        """
        Publishes a post to a GitHub Pages Jekyll repository via Git.
        Returns the estimated URL of the post.
        """
        if not self.github_creds or not self.github_creds.get("token"):
             print("⚠️ [BlogManager] GitHub token missing.")
             self._save_local_draft(title, content, [], "github")
             return None

        # Temp directory for cloning
        temp_dir = Path(os.environ.get("TEMP", "/tmp")) / "gh_pages_publish"
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Inject token into URL for auth
            # repo_url format: https://github.com/user/repo.git -> https://user:token@github.com/user/repo.git
            if "https://" in repo_url:
                auth_repo_url = repo_url.replace("https://", f"https://{self.github_creds['username']}:{self.github_creds['token']}@")
            else:
                auth_repo_url = repo_url

            print(f"running git clone {repo_url}...")
            subprocess.run(["git", "clone", auth_repo_url, "."], cwd=temp_dir, check=True, capture_output=True)
            
            # Configure Git
            subprocess.run(["git", "config", "user.name", "AutoBot"], cwd=temp_dir, check=True)
            subprocess.run(["git", "config", "user.email", "bot@automated.com"], cwd=temp_dir, check=True)
            
            # Create Post File
            # Jekyll format: _posts/YYYY-MM-DD-slug.md
            date_str = datetime.now().strftime("%Y-%m-%d")
            slug = filename.replace(".md", "").replace(" ", "-").lower()
            post_filename = f"{date_str}-{slug}.md"
            
            posts_dir = temp_dir / "_posts"
            posts_dir.mkdir(exist_ok=True)
            
            post_path = posts_dir / post_filename
            
            # Jekyll Front Matter
            front_matter = f"---\nlayout: post\ntitle: \"{title}\"\ndate: {date_str}\n---\n\n"
            final_content = front_matter + content
            
            post_path.write_text(final_content, encoding="utf-8")
            
            # Commit and Push
            subprocess.run(["git", "add", "."], cwd=temp_dir, check=True)
            subprocess.run(["git", "commit", "-m", f"Add post: {title}"], cwd=temp_dir, check=True)
            subprocess.run(["git", "push"], cwd=temp_dir, check=True)
            
            print(f"✅ [BlogManager] Pushed to GitHub Pages: {post_filename}")
            
            # Construct estimated URL (assuming standard Jekyll permalink structure)
            # This is a guess, but better than nothing.
            # User/Repo -> https://User.github.io/Repo/YYYY/MM/DD/slug.html
            try:
                username = self.github_creds['username']
                repo_name = repo_url.split("/")[-1].replace(".git", "")
                if "github.io" in repo_name and repo_name == f"{username}.github.io":
                    base_url = f"https://{username}.github.io"
                else:
                    base_url = f"https://{username}.github.io/{repo_name}"
                
                # Default Jekyll Permalink: /:categories/:year/:month/:day/:title/
                # We don't know the permalink structure, but let's assume date based.
                url_slug = post_filename.replace(".md", "").replace(f"{date_str}-", "")
                year, month, day = date_str.split("-")
                post_url = f"{base_url}/{year}/{month}/{day}/{url_slug}.html"
                return post_url
            except:
                return f"https://github.com/{self.github_creds['username']}/{repo_name}/blob/main/_posts/{post_filename}"

        except subprocess.CalledProcessError as e:
            print(f"❌ [BlogManager] Git error: {e}")
            if e.stderr:
                print(f"   Stderr: {e.stderr.decode('utf-8', errors='ignore')}")
            return None
        except Exception as e:
            print(f"❌ [BlogManager] Error publishing to GitHub Pages: {e}")
            return None
        finally:
            # Cleanup
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
            except:
                pass


    def _save_local_draft(self, title: str, content: str, tags: list, platform: str):
        """
        Saves the post as a markdown file for manual publishing.
        """
        filename = f"draft_{platform}_{title.replace(' ', '_')[:20]}.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"---\nTitle: {title}\nTags: {', '.join(tags)}\nPlatform: {platform}\n---\n\n{content}")
        print(f"📝 [BlogManager] Draft saved to {filename}")

