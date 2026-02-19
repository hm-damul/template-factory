import requests
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("MediumClient")

class MediumClient:
    BASE_URL = "https://api.medium.com/v1"

    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Charset": "utf-8"
        }
        self.user_id = None

    def get_user_id(self) -> Optional[str]:
        if self.user_id:
            return self.user_id
        
        try:
            resp = requests.get(f"{self.BASE_URL}/me", headers=self.headers, timeout=10)
            if resp.status_code == 401:
                logger.error("Medium API Token is invalid or expired.")
                return None
            resp.raise_for_status()
            data = resp.json()
            self.user_id = data["data"]["id"]
            return self.user_id
        except Exception as e:
            logger.error(f"Failed to get Medium user ID: {e}")
            return None

    def create_post(self, title: str, content: str, content_format: str = "markdown", 
                    tags: List[str] = None, canonical_url: str = None, 
                    publish_status: str = "draft", notify_followers: bool = True) -> Dict[str, Any]:
        """
        Create a post on Medium.
        
        Args:
            title: The title of the post.
            content: The body of the post.
            content_format: 'html' or 'markdown'.
            tags: List of tags (max 5).
            canonical_url: Original URL if reposting.
            publish_status: 'public', 'draft', or 'unlisted'.
            notify_followers: Whether to notify followers (default True).
        """
        uid = self.get_user_id()
        if not uid:
            return {"error": "Could not retrieve user ID", "success": False}

        url = f"{self.BASE_URL}/users/{uid}/posts"
        
        # Medium allows max 5 tags
        valid_tags = (tags or [])[:5]
        
        payload = {
            "title": title,
            "contentFormat": content_format, # html or markdown
            "content": content,
            "tags": valid_tags,
            "publishStatus": publish_status,
            "notifyFollowers": notify_followers
        }
        
        if canonical_url:
            payload["canonicalUrl"] = canonical_url

        try:
            resp = requests.post(url, headers=self.headers, json=payload, timeout=30)
            
            if resp.status_code >= 400:
                logger.error(f"Medium API Error: {resp.status_code} - {resp.text}")
                return {"success": False, "error": resp.text, "status_code": resp.status_code}
                
            data = resp.json()
            return {"success": True, "data": data["data"]}
            
        except Exception as e:
            logger.error(f"Failed to create Medium post: {e}")
            return {"success": False, "error": str(e)}
