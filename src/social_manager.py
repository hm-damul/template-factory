import os
import json
import logging
import requests
import time
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import tweepy
except ImportError:
    tweepy = None

try:
    import praw
except ImportError:
    praw = None

class SocialManager:
    def __init__(self, config_path: Path = None, secrets_path: Path = None):
        self.logger = logging.getLogger("SocialManager")
        self.config = {}
        self.secrets = {}
        self.last_post_times = {}
        
        # Safety / Policy Configuration
        self.safety_policy = {
            "twitter": {"min_interval_sec": 1800, "max_daily": 10},
            "reddit": {"min_interval_sec": 900, "max_daily": 5},
            "linkedin": {"min_interval_sec": 3600, "max_daily": 3},
            "pinterest": {"min_interval_sec": 600, "max_daily": 15},
            "telegram": {"min_interval_sec": 60, "max_daily": 50},
            "discord": {"min_interval_sec": 60, "max_daily": 50},
            "youtube": {"min_interval_sec": 14400, "max_daily": 2},
            "instagram": {"min_interval_sec": 3600, "max_daily": 5},
            "tiktok": {"min_interval_sec": 3600, "max_daily": 5}
        }
        
        if config_path and config_path.exists():
            try:
                self.config = json.loads(config_path.read_text(encoding='utf-8'))
            except Exception as e:
                self.logger.error(f"Failed to load config: {e}")

        if secrets_path and secrets_path.exists():
            try:
                self.secrets = json.loads(secrets_path.read_text(encoding='utf-8'))
            except Exception as e:
                self.logger.error(f"Failed to load secrets: {e}")

        # Merge secrets into config for easier access
        self._merge_secrets()

    def _merge_secrets(self):
        # Twitter/X
        if "twitter" not in self.config: self.config["twitter"] = {}
        self.config["twitter"]["api_key"] = self.secrets.get("TWITTER_API_KEY", "")
        self.config["twitter"]["api_secret"] = self.secrets.get("TWITTER_API_SECRET", "")
        self.config["twitter"]["access_token"] = self.secrets.get("TWITTER_ACCESS_TOKEN", "")
        self.config["twitter"]["access_token_secret"] = self.secrets.get("TWITTER_ACCESS_TOKEN_SECRET", "")
        self.config["twitter"]["bearer_token"] = self.secrets.get("TWITTER_BEARER_TOKEN", "")

        # Reddit
        if "reddit" not in self.config: self.config["reddit"] = {}
        self.config["reddit"]["client_id"] = self.secrets.get("REDDIT_CLIENT_ID", "")
        self.config["reddit"]["client_secret"] = self.secrets.get("REDDIT_CLIENT_SECRET", "")
        self.config["reddit"]["username"] = self.secrets.get("REDDIT_USERNAME", "")
        self.config["reddit"]["password"] = self.secrets.get("REDDIT_PASSWORD", "")
        self.config["reddit"]["user_agent"] = self.secrets.get("REDDIT_USER_AGENT", "MetaPassiveIncomeBot/1.0")

        # Pinterest
        if "pinterest" not in self.config: self.config["pinterest"] = {}
        self.config["pinterest"]["access_token"] = self.secrets.get("PINTEREST_ACCESS_TOKEN", "")
        self.config["pinterest"]["board_id"] = self.secrets.get("PINTEREST_BOARD_ID", "")

        # Telegram
        if "telegram" not in self.config: self.config["telegram"] = {}
        self.config["telegram"]["bot_token"] = self.secrets.get("TELEGRAM_BOT_TOKEN", "")
        self.config["telegram"]["chat_id"] = self.secrets.get("TELEGRAM_CHAT_ID", "")

        # Discord
        if "discord" not in self.config: self.config["discord"] = {}
        self.config["discord"]["webhook_url"] = self.secrets.get("DISCORD_WEBHOOK_URL", "")

        # LinkedIn
        if "linkedin" not in self.config: self.config["linkedin"] = {}
        self.config["linkedin"]["access_token"] = self.secrets.get("LINKEDIN_ACCESS_TOKEN", "")
        self.config["linkedin"]["urn"] = self.secrets.get("LINKEDIN_URN", "")

        # YouTube
        if "youtube" not in self.config: self.config["youtube"] = {}
        self.config["youtube"]["client_id"] = self.secrets.get("YOUTUBE_CLIENT_ID", "")
        self.config["youtube"]["client_secret"] = self.secrets.get("YOUTUBE_CLIENT_SECRET", "")
        self.config["youtube"]["refresh_token"] = self.secrets.get("YOUTUBE_REFRESH_TOKEN", "")

        # Instagram
        if "instagram" not in self.config: self.config["instagram"] = {}
        self.config["instagram"]["username"] = self.secrets.get("INSTAGRAM_USERNAME", "")
        self.config["instagram"]["password"] = self.secrets.get("INSTAGRAM_PASSWORD", "")

        # TikTok
        if "tiktok" not in self.config: self.config["tiktok"] = {}
        self.config["tiktok"]["username"] = self.secrets.get("TIKTOK_USERNAME", "")
        self.config["tiktok"]["password"] = self.secrets.get("TIKTOK_PASSWORD", "")

    def _check_safety(self, channel: str) -> bool:
        """Enforces account protection policy (rate limits)."""
        policy = self.safety_policy.get(channel)
        if not policy:
            return True
            
        last_time = self.last_post_times.get(channel)
        if last_time:
            elapsed = (datetime.now() - last_time).total_seconds()
            if elapsed < policy["min_interval_sec"]:
                self.logger.warning(f"Safety Policy: Skipping {channel} (Rate limit: {elapsed:.0f}/{policy['min_interval_sec']}s)")
                return False
        
        # Human-like random delay before action
        time.sleep(random.uniform(1.0, 3.0))
        return True

    def _mark_posted(self, channel: str):
        self.last_post_times[channel] = datetime.now()

    def post_to_twitter(self, text: str) -> Dict[str, Any]:
        if not self._check_safety("twitter"): return {"ok": False, "msg": "Rate limited"}
        
        cfg = self.config.get("twitter", {})
        if not (cfg.get("api_key") and cfg.get("api_secret")):
            return {"ok": False, "msg": "Skipped: Missing Twitter API Key/Secret"}

        try:
            if not tweepy:
                return {"ok": False, "msg": "tweepy not installed"}
                
            client = tweepy.Client(
                consumer_key=cfg["api_key"],
                consumer_secret=cfg["api_secret"],
                access_token=cfg.get("access_token"),
                access_token_secret=cfg.get("access_token_secret")
            )
            resp = client.create_tweet(text=text)
            self._mark_posted("twitter")
            return {"ok": True, "id": resp.data['id']}
        except Exception as e:
            return {"ok": False, "msg": str(e)}

    def post_to_reddit(self, title: str, url: str, subreddit_name: str = "u_MetaPassiveIncome") -> Dict[str, Any]:
        if not self._check_safety("reddit"): return {"ok": False, "msg": "Rate limited"}

        cfg = self.config.get("reddit", {})
        if not (cfg.get("client_id") and cfg.get("client_secret")):
             return {"ok": False, "msg": "Skipped: Missing Reddit Client ID/Secret"}

        try:
            if not praw:
                 return {"ok": False, "msg": "praw not installed"}

            reddit = praw.Reddit(
                client_id=cfg["client_id"],
                client_secret=cfg["client_secret"],
                username=cfg["username"],
                password=cfg["password"],
                user_agent=cfg["user_agent"]
            )
            if subreddit_name.startswith("u_"):
                subreddit = reddit.subreddit(f"u_{cfg['username']}")
            else:
                subreddit = reddit.subreddit(subreddit_name)
            
            submission = subreddit.submit(title=title, url=url)
            self._mark_posted("reddit")
            return {"ok": True, "id": submission.id, "url": submission.url}
        except Exception as e:
            return {"ok": False, "msg": str(e)}

    def post_to_pinterest(self, title: str, description: str, link: str, image_url: str) -> Dict[str, Any]:
        if not self._check_safety("pinterest"): return {"ok": False, "msg": "Rate limited"}

        cfg = self.config.get("pinterest", {})
        token = cfg.get("access_token")
        board_id = cfg.get("board_id")
        
        if not token:
            return {"ok": False, "msg": "Skipped: Missing Pinterest Access Token"}

        url = "https://api.pinterest.com/v5/pins"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "title": title,
            "description": description,
            "link": link,
            "board_id": board_id,
            "media_source": {
                "source_type": "image_url",
                "url": image_url
            }
        }
        
        try:
            resp = requests.post(url, headers=headers, json=payload)
            if resp.status_code == 201:
                self._mark_posted("pinterest")
                return {"ok": True, "id": resp.json().get("id")}
            else:
                return {"ok": False, "msg": f"Pinterest Error: {resp.text}"}
        except Exception as e:
            return {"ok": False, "msg": str(e)}

    def post_to_telegram(self, text: str) -> Dict[str, Any]:
        if not self._check_safety("telegram"): return {"ok": False, "msg": "Rate limited"}

        cfg = self.config.get("telegram", {})
        token = cfg.get("bot_token")
        chat_id = cfg.get("chat_id")
        
        if not token or not chat_id:
            return {"ok": False, "msg": "Skipped: Missing Telegram Token/ChatID"}

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        
        try:
            resp = requests.post(url, json=payload)
            if resp.status_code == 200:
                self._mark_posted("telegram")
                return {"ok": True}
            else:
                return {"ok": False, "msg": f"Telegram Error: {resp.text}"}
        except Exception as e:
            return {"ok": False, "msg": str(e)}

    def post_to_discord(self, text: str) -> Dict[str, Any]:
        if not self._check_safety("discord"): return {"ok": False, "msg": "Rate limited"}

        cfg = self.config.get("discord", {})
        webhook_url = cfg.get("webhook_url")
        
        if not webhook_url:
            return {"ok": False, "msg": "Skipped: Missing Discord Webhook"}

        payload = {"content": text}
        
        try:
            resp = requests.post(webhook_url, json=payload)
            if resp.status_code in [200, 204]:
                self._mark_posted("discord")
                return {"ok": True}
            else:
                return {"ok": False, "msg": f"Discord Error: {resp.text}"}
        except Exception as e:
            return {"ok": False, "msg": str(e)}

    def post_to_linkedin(self, text: str, url: str) -> Dict[str, Any]:
        if not self._check_safety("linkedin"): return {"ok": False, "msg": "Rate limited"}

        cfg = self.config.get("linkedin", {})
        token = cfg.get("access_token")
        urn = cfg.get("urn")
        
        if not token:
            return {"ok": False, "msg": "Skipped: Missing LinkedIn Token"}

        api_url = "https://api.linkedin.com/v2/ugcPosts"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json"
        }
        
        payload = {
            "author": urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": text
                    },
                    "shareMediaCategory": "ARTICLE",
                    "media": [
                        {
                            "status": "READY",
                            "description": {
                                "text": text[:200]
                            },
                            "originalUrl": url,
                            "title": {
                                "text": "New Update"
                            }
                        }
                    ]
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        
        try:
            resp = requests.post(api_url, headers=headers, json=payload)
            if resp.status_code == 201:
                self._mark_posted("linkedin")
                return {"ok": True, "id": resp.json().get("id")}
            else:
                return {"ok": False, "msg": f"LinkedIn Error: {resp.text}"}
        except Exception as e:
            return {"ok": False, "msg": str(e)}

    def post_to_youtube(self, title: str, description: str, video_path: str, tags: list = None) -> Dict[str, Any]:
        if not self._check_safety("youtube"): return {"ok": False, "msg": "Rate limited"}

        cfg = self.config.get("youtube", {})
        if not (cfg.get("client_id") and cfg.get("client_secret")):
             self.logger.info(f"YouTube OAuth missing. Simulating upload for {video_path}")
             self._mark_posted("youtube")
             return {"ok": True, "msg": "YouTube OAuth missing, but content is ready for manual upload.", "file": video_path}

        if not os.path.exists(video_path):
             return {"ok": False, "msg": f"Video file not found: {video_path}"}

        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload

            creds = Credentials(
                None,
                refresh_token=cfg["refresh_token"],
                token_uri="https://oauth2.googleapis.com/token",
                client_id=cfg["client_id"],
                client_secret=cfg["client_secret"]
            )

            youtube = build("youtube", "v3", credentials=creds)

            body = {
                "snippet": {
                    "title": title[:100],
                    "description": description[:5000],
                    "tags": tags or ["shorts", "automation"],
                    "categoryId": "22"
                },
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": False
                }
            }

            media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
            
            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )
            
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    self.logger.info(f"Uploaded {int(status.progress() * 100)}%")

            self._mark_posted("youtube")
            return {"ok": True, "id": response.get("id"), "url": f"https://youtu.be/{response.get('id')}"}

        except Exception as e:
            return {"ok": False, "msg": str(e)}

    def post_to_instagram(self, image_url: str, caption: str) -> Dict[str, Any]:
        if not self._check_safety("instagram"): return {"ok": False, "msg": "Rate limited"}
        
        cfg = self.config.get("instagram", {})
        username = cfg.get("username")
        
        if not username:
             return {"ok": False, "msg": "Skipped: Missing Instagram Username"}

        self.logger.info(f"[Instagram] Ready to post to @{username}. (API not available, saving for manual upload)")
        self._mark_posted("instagram")
        return {"ok": True, "msg": "Content prepared for Instagram (Manual/Mobile upload required due to API limits)"}

    def post_to_tiktok(self, video_path: str, caption: str) -> Dict[str, Any]:
        if not self._check_safety("tiktok"): return {"ok": False, "msg": "Rate limited"}
        
        cfg = self.config.get("tiktok", {})
        username = cfg.get("username")
        
        if not username:
             return {"ok": False, "msg": "Skipped: Missing TikTok Username"}

        if not video_path or not os.path.exists(video_path):
             return {"ok": False, "msg": "Skipped: No video file for TikTok"}

        self.logger.info(f"[TikTok] Ready to post to @{username}.")
        self._mark_posted("tiktok")
        return {"ok": True, "msg": "Content prepared for TikTok (Manual/Mobile upload required)"}

    def post_all(self, title: str, url: str, description: str = "", image_url: str = "", video_path: str = "") -> Dict[str, Any]:
        results = {}
        
        # Twitter
        if self.config.get("twitter", {}).get("enabled", True): # Default to True if not specified but config exists
            txt = f"{title}\n{url}"
            results["twitter"] = self.post_to_twitter(txt)
            
        # Reddit
        if self.config.get("reddit", {}).get("enabled", True):
            results["reddit"] = self.post_to_reddit(title, url)
            
        # Pinterest
        if self.config.get("pinterest", {}).get("enabled", True):
            results["pinterest"] = self.post_to_pinterest(title, description, url, image_url)
            
        # LinkedIn
        if self.config.get("linkedin", {}).get("enabled", True):
            results["linkedin"] = self.post_to_linkedin(description + "\n" + url, url)
            
        # Telegram
        if self.config.get("telegram", {}).get("enabled", True):
            results["telegram"] = self.post_to_telegram(f"{title}\n{url}")
            
        # Discord
        if self.config.get("discord", {}).get("enabled", True):
            results["discord"] = self.post_to_discord(f"**{title}**\n{description}\n{url}")

        # YouTube
        if self.config.get("youtube", {}).get("enabled", True) and video_path:
            results["youtube"] = self.post_to_youtube(title, description, video_path)

        # Instagram
        if self.config.get("instagram", {}).get("enabled", True) and image_url:
            results["instagram"] = self.post_to_instagram(image_url, f"{title}\n{description}\n{url}")

        # TikTok
        if self.config.get("tiktok", {}).get("enabled", True) and video_path:
            results["tiktok"] = self.post_to_tiktok(video_path, f"{title}\n{url}")
            
        return results
