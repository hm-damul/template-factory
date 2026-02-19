
import os
import sys
import json
import logging
import random
import time
import requests
from pathlib import Path
from typing import Dict, Any, List

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from src.social_manager import SocialManager
from src.blog_manager import BlogManager
from src.ledger_manager import LedgerManager
from src.publisher import Publisher
from src.config import Config

class AIPromoBot:
    def __init__(self):
        self.logger = logging.getLogger("AIPromoBot")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            ch.setFormatter(formatter)
            self.logger.addHandler(ch)

        self.project_root = Path(__file__).resolve().parents[1]
        self.data_dir = self.project_root / "data"
        self.secrets_path = self.data_dir / "secrets.json"
        self.config_path = self.data_dir / "promo_channels.json"
        self.history_path = self.data_dir / "promo_history.json"
        
        # Load secrets
        self.secrets = {}
        if self.secrets_path.exists():
            try:
                self.secrets = json.loads(self.secrets_path.read_text(encoding="utf-8"))
            except Exception as e:
                self.logger.error(f"Failed to load secrets: {e}")
        
        # Log Credential Usage
        self.logger.info("Loaded credentials: xmdnlxjqkdthd@gmail.com (Used for authentication where applicable)")

        # Initialize Managers
        self.social = SocialManager(self.config_path, self.secrets_path)
        
        # Initialize BlogManager with credentials from secrets if available
        medium_token = self.secrets.get("MEDIUM_TOKEN")
        tumblr_creds = {
            "consumer_key": self.secrets.get("TUMBLR_CONSUMER_KEY"),
            "consumer_secret": self.secrets.get("TUMBLR_CONSUMER_SECRET"),
            "oauth_token": self.secrets.get("TUMBLR_OAUTH_TOKEN"),
            "oauth_token_secret": self.secrets.get("TUMBLR_OAUTH_SECRET")
        } if self.secrets.get("TUMBLR_CONSUMER_KEY") else None
        
        self.blog = BlogManager(
            medium_token=medium_token,
            tumblr_creds=tumblr_creds
        )
        
        self.ledger = LedgerManager(Config.DATABASE_URL)
        self.publisher = Publisher(self.ledger)
        
        self.history = self._load_history()

    def _load_history(self) -> Dict:
        if self.history_path.exists():
            try:
                return json.loads(self.history_path.read_text(encoding="utf-8"))
            except:
                return {}
        return {}

    def _save_history(self):
        try:
            self.history_path.write_text(json.dumps(self.history, indent=2), encoding="utf-8")
        except Exception as e:
            self.logger.error(f"Failed to save history: {e}")

    def _generate_variations(self, title: str, description: str, price: float, url: str) -> Dict[str, str]:
        """
        Simulates AI-based content variation for different platforms.
        """
        
        # Twitter (Short, Hashtags)
        twitter_templates = [
            f"🚀 Just launched: {title}!\n\nGet it now for ${price} only.\n\n👉 {url}\n\n#DigitalProducts #PassiveIncome #SaaS",
            f"🔥 Don't miss out on {title}.\n\nThe ultimate tool for your business.\n\nGrab it here: {url}\n#Business #Growth",
            f"💎 New Drop: {title}\n\nBoost your productivity today!\n\n🔗 {url}",
            f"Stop wasting time. {title} is here to help.\n\nCheck it out: {url}"
        ]
        
        # LinkedIn (Professional, Value-focused)
        linkedin_templates = [
            f"Excited to announce the release of {title}.\n\nThis tool is designed to help professionals streamline their workflow and achieve better results.\n\nKey Benefits:\n✅ High Quality\n✅ Instant Access\n✅ Commercial License\n\nLearn more: {url}",
            f"Are you looking to improve your business efficiency?\n\nCheck out {title}. It's a game-changer for digital entrepreneurs.\n\nAvailable now: {url}\n\n#Entrepreneurship #DigitalAssets #BusinessTools"
        ]
        
        # Reddit (Community-focused, Question-style)
        reddit_titles = [
            f"Has anyone tried {title}? Just released.",
            f"Showcase: {title} - A new tool for digital creators",
            f"[Release] {title} - Now available for ${price}",
            f"What do you think about {title}?"
        ]
        
        # TikTok/Shorts (Engaging, short)
        tiktok_captions = [
            f"Wait for it... {title} is here! #fyp #business #tools",
            f"Stop doing this manually. Use {title} instead. Link in bio! #automation",
            f"The secret to {title}. Get it now: {url}"
        ]
        
        # Instagram (Visual, hashtags)
        insta_captions = [
             f"New Arrival: {title} ✨\n\n{description[:100]}...\n\nGrab yours at the link in bio! 🔗\n\n#SmallBusiness #DigitalProducts #Growth",
             f"Upgrade your workflow with {title}. 🚀\n\nAvailable now for only ${price}.\n\n#Entrepreneur #Hustle #Tech"
        ]
        
        return {
            "twitter": random.choice(twitter_templates),
            "linkedin": random.choice(linkedin_templates),
            "reddit_title": random.choice(reddit_titles),
            "reddit_url": url,
            "tiktok": random.choice(tiktok_captions),
            "instagram": random.choice(insta_captions)
        }

    def _verify_url(self, url: str) -> bool:
        try:
            r = requests.head(url, timeout=5)
            return r.status_code == 200
        except:
            return False

    def promote_product(self, product_id: str):
        """
        Promotes a single product across all enabled channels.
        """
        self.logger.info(f"Starting promotion for product {product_id}...")
        
        # Check History
        if product_id in self.history and self.history[product_id].get("fully_promoted"):
            self.logger.info(f"Product {product_id} already fully promoted. Skipping.")
            return

        product = self.ledger.get_product(product_id)
        if not product:
            self.logger.error(f"Product {product_id} not found.")
            return
            
        meta = product.get("metadata") or {}
        if isinstance(meta, str):
            meta = json.loads(meta)
            
        title = product.get("topic") or meta.get("title") or "Digital Product"
        desc = meta.get("description") or f"A premium digital asset: {title}"
        price = float(meta.get("price_usd") or 29.00)
        url = meta.get("deployment_url")
        
        # Fallback URL construction & Recovery
        if not url or not self._verify_url(url):
            self.logger.warning(f"URL missing or invalid for {product_id}. Attempting recovery...")
            
            # 1. Try to find local output dir
            output_dir = self.project_root / "outputs" / product_id
            if output_dir.exists():
                try:
                    # 2. Deploy via Git (Publisher)
                    self.logger.info(f"Deploying {product_id} via Git Push...")
                    res = self.publisher.publish_product(product_id, str(output_dir))
                    if res.get("status") == "PUBLISHED":
                        url = res.get("url")
                        self.logger.info(f"Recovered URL: {url}")
                except Exception as e:
                    self.logger.error(f"Recovery failed: {e}")
            else:
                self.logger.error(f"Output directory not found for {product_id}")

        if not url:
             self.logger.error(f"Final check: No valid URL for {product_id}. Skipping promotion.")
             return

        # Generate Content
        content = self._generate_variations(title, desc, price, url)
        
        # 1. Social Media
        results = {}
        
        # Twitter
        res = self.social.post_to_twitter(content["twitter"])
        results["twitter"] = res
        if res["ok"]:
            self.logger.info(f"✅ Posted to Twitter: {res.get('id')}")
        else:
            self.logger.warning(f"⚠️ Twitter: {res.get('msg')}")
            
        # LinkedIn
        res = self.social.post_to_linkedin(content["linkedin"], url)
        results["linkedin"] = res
        if res["ok"]:
            self.logger.info(f"✅ Posted to LinkedIn: {res.get('id')}")
        else:
            self.logger.warning(f"⚠️ LinkedIn: {res.get('msg')}")
            
        # Reddit
        res = self.social.post_to_reddit(content["reddit_title"], url)
        results["reddit"] = res
        if res["ok"]:
            self.logger.info(f"✅ Posted to Reddit: {res.get('id')}")
        else:
            self.logger.warning(f"⚠️ Reddit: {res.get('msg')}")

        # Pinterest (Need Image)
        img_url = meta.get("image_url")
        if img_url:
            res = self.social.post_to_pinterest(title, desc, url, img_url)
            results["pinterest"] = res
            if res["ok"]:
                self.logger.info(f"✅ Posted to Pinterest: {res.get('id')}")
            else:
                self.logger.warning(f"⚠️ Pinterest: {res.get('msg')}")
        else:
             self.logger.info("ℹ️ Pinterest skipped (No image URL)")

        # Check for local media
        output_dir = self.project_root / "outputs" / product_id
        video_path = str(output_dir / "video.mp4") if (output_dir / "video.mp4").exists() else ""
        image_path = str(output_dir / "public" / "cover.png") if (output_dir / "public" / "cover.png").exists() else ""

        # YouTube Shorts (Video)
        if video_path:
            self.logger.info(f"Found video for {product_id}. Attempting YouTube/TikTok...")
            res = self.social.post_to_youtube(title, desc, video_path)
            results["youtube"] = res
            if res["ok"]:
                 self.logger.info(f"✅ YouTube: {res.get('msg') or res.get('id')}")
            else:
                 self.logger.warning(f"⚠️ YouTube: {res.get('msg')}")

            # TikTok (Video)
            res = self.social.post_to_tiktok(video_path, content["tiktok"])
            results["tiktok"] = res
            if res["ok"]:
                 self.logger.info(f"✅ TikTok: {res.get('msg')}")
            else:
                 self.logger.warning(f"⚠️ TikTok: {res.get('msg')}")
        else:
            self.logger.info("ℹ️ Video channels skipped (No video.mp4 found)")

        # Instagram (Image)
        if image_path:
            res = self.social.post_to_instagram(image_path, content["instagram"])
            results["instagram"] = res
            if res["ok"]:
                 self.logger.info(f"✅ Instagram: {res.get('msg')}")
            else:
                 self.logger.warning(f"⚠️ Instagram: {res.get('msg')}")
        else:
            self.logger.info("ℹ️ Instagram skipped (No local cover.png found)")

        # 2. Blog Expansion (Medium, etc.)
        blog_content = f"# {title}\n\n{desc}\n\n[Get it now]({url})\n\nPrice: ${price}"
        tags = ["digital products", "business", "software", "templates"]
        
        # Medium
        m_url = self.blog.publish_medium(title, blog_content, tags, canonical_url=url)
        if m_url:
            results["medium"] = {"ok": True, "url": m_url}
        else:
            results["medium"] = {"ok": False, "msg": "Failed or skipped"}

        # Update History
        self.history[product_id] = {
            "last_promoted": time.time(),
            "results": results,
            "url": url,
            "fully_promoted": all(r.get("ok") for r in results.values() if "msg" not in r or "Skipped" not in r["msg"])
        }
        self._save_history()

        return results

    def promote_all_active(self, limit: int = None):
        """
        Promotes all products that have a deployment URL (or can be constructed).
        """
        products = self.ledger.get_all_products()
        count = 0
        processed = 0
        
        # Shuffle to random order to avoid always failing on the same ones
        random.shuffle(products)
        
        for p in products:
            if limit and processed >= limit:
                break
                
            try:
                self.promote_product(p['id'])
                count += 1
                processed += 1
                # Human-like delay between products
                sleep_time = random.randint(10, 30)
                self.logger.info(f"Sleeping for {sleep_time}s...")
                time.sleep(sleep_time)
            except Exception as e:
                self.logger.error(f"Error promoting {p.get('id')}: {e}")
                
        self.logger.info(f"Finished promoting {count} products.")

if __name__ == "__main__":
    bot = AIPromoBot()
    # Run for all products
    bot.promote_all_active(limit=None)

