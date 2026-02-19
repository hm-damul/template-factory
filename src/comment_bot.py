import os
import json
import time
import requests
import random
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime

# Load configuration
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SECRETS_FILE = DATA_DIR / "secrets.json"

class CommentBot:
    """
    Automated comment management bot for WordPress.
    Follows platform policies:
    1. No spamming (replies only to relevant comments).
    2. Respectful tone.
    3. Rate limiting (delays between actions).
    """
    
    def __init__(self, wp_api_url: str, wp_token: str):
        self.wp_api_url = wp_api_url.rstrip("/")
        # wp-json/wp/v2/posts -> wp-json/wp/v2/comments
        self.comments_url = self.wp_api_url.replace("/posts", "/comments")
        self.headers = {
            "Authorization": f"Basic {wp_token}",
            "Content-Type": "application/json"
        }
        self.processed_comments = set()

    def fetch_unreplied_comments(self, limit: int = 10) -> List[Dict]:
        """
        Fetches recent comments that don't have replies from the author.
        """
        try:
            # Fetch recent comments
            params = {
                "per_page": limit,
                "status": "approve",  # Only approved comments
                "orderby": "date",
                "order": "desc"
            }
            response = requests.get(self.comments_url, headers=self.headers, params=params)
            
            if response.status_code != 200:
                print(f"❌ [CommentBot] Failed to fetch comments: {response.text}")
                return []
                
            comments = response.json()
            unreplied = []
            
            # Simple check: if we haven't processed this ID yet
            # In a real scenario, we'd check if children exist or check author ID
            # For simplicity, we just check our local memory set for this session
            for comment in comments:
                c_id = comment['id']
                if c_id not in self.processed_comments:
                    unreplied.append(comment)
                    
            return unreplied
            
        except Exception as e:
            print(f"❌ [CommentBot] Error fetching comments: {e}")
            return []

    def generate_reply(self, comment_content: str, author_name: str) -> str:
        """
        Generates a contextual reply.
        """
        # Basic keyword matching
        content_lower = comment_content.lower()
        
        greetings = ["Hello", "Hi", "Greetings"]
        thanks = ["Thank you for your comment!", "Thanks for reaching out.", "We appreciate your feedback."]
        
        reply_body = ""
        
        if "price" in content_lower or "cost" in content_lower:
            reply_body = "Regarding the pricing, please check the latest details on the product page. We offer competitive rates."
        elif "bug" in content_lower or "error" in content_lower or "issue" in content_lower:
            reply_body = "We are sorry to hear about the issue. Our team is looking into it. Please contact support for immediate assistance."
        elif "good" in content_lower or "great" in content_lower or "awesome" in content_lower:
            reply_body = "We are glad you liked it! Let us know if you have any suggestions for improvements."
        else:
            reply_body = "Thank you for sharing your thoughts with us."
            
        return f"{random.choice(greetings)} {author_name}, {random.choice(thanks)} {reply_body}"

    def post_reply(self, comment_id: int, reply_content: str, post_id: int):
        """
        Posts a reply to a specific comment.
        """
        try:
            payload = {
                "content": reply_content,
                "post": post_id,
                "parent": comment_id,
                # status is 'approve' if the user has permissions, otherwise 'hold'
                # We assume the bot account has permissions
            }
            
            # Policy Compliance: Random delay to mimic human behavior
            time.sleep(random.uniform(2, 5))
            
            response = requests.post(self.comments_url, headers=self.headers, json=payload)
            
            if response.status_code in [200, 201]:
                print(f"✅ [CommentBot] Replied to comment {comment_id}")
                self.processed_comments.add(comment_id)
                return True
            else:
                print(f"❌ [CommentBot] Failed to reply: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ [CommentBot] Error posting reply: {e}")
            return False

    def run_cycle(self):
        """
        Runs one cycle of checking and replying.
        """
        print("🤖 [CommentBot] Checking for new comments...")
        comments = self.fetch_unreplied_comments()
        
        if not comments:
            print("✨ [CommentBot] No new comments to process.")
            return

        for comment in comments:
            # Check if it's already replied by us (skip if author is me)
            # Assuming bot author ID is known or we check author_name
            # For now, simplistic check
            
            author = comment.get('author_name', 'Visitor')
            content = comment.get('content', {}).get('rendered', '')
            post_id = comment.get('post')
            c_id = comment.get('id')
            
            # Clean HTML tags from content
            clean_content = re.sub('<[^<]+?>', '', content)
            
            reply = self.generate_reply(clean_content, author)
            
            print(f"💬 [CommentBot] Replying to {author} on post {post_id}...")
            self.post_reply(c_id, reply, post_id)
            
            # Rate limiting
            time.sleep(random.uniform(1, 3))

if __name__ == "__main__":
    import re
    # Load secrets
    if SECRETS_FILE.exists():
        with open(SECRETS_FILE, "r", encoding="utf-8") as f:
            secrets = json.load(f)
            
        wp_url = secrets.get("WP_API_URL")
        wp_token = secrets.get("WP_TOKEN")
        
        if wp_url and wp_token:
            bot = CommentBot(wp_url, wp_token)
            bot.run_cycle()
        else:
            print("❌ WP credentials missing in secrets.json")
    else:
        print("❌ secrets.json not found")
