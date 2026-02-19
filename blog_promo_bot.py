import time
import json
import threading
from pathlib import Path
from src.ledger_manager import LedgerManager
from src.config import Config
from promotion_dispatcher import dispatch_publish

PROJECT_ROOT = Path(__file__).resolve().parent
BLOG_CHANNELS = [
    "medium", "tumblr", "github_pages", "wordpress", "blogger",
    "x", "telegram", "discord", "reddit", "pinterest", "linkedin",
    "youtube_shorts", "instagram", "tiktok"
]

class BlogPromoBot:
    def __init__(self):
        self.running = False
        self.logs = []
        self.thread = None
        self.max_logs = 100

    def log(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] {message}"
        print(entry)
        self.logs.append(entry)
        if len(self.logs) > self.max_logs:
            self.logs.pop(0)

    def get_logs(self):
        # Return logs in reverse order (newest first)
        return list(reversed(self.logs))

    def is_running(self):
        return self.running

    def start(self):
        if self.running:
            self.log("[WARN] Bot is already running.")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        self.log("[Bot] Blog Promotion Bot Started.")

    def stop(self):
        if not self.running:
            return
        self.running = False
        self.log("[STOP] Stopping bot...")
        # Thread will exit on next loop check
        # We don't join here to avoid blocking the web server request if it takes time
        self.log("[STOP] Bot stop signal sent.")

    def _get_unpromoted_blogs(self, product_id: str, lm: LedgerManager) -> list:
        prod = lm.get_product(product_id)
        if not prod:
            return []
        
        meta = prod.get("metadata") or {}
        needed = []
        
        if not meta.get("medium_url"): needed.append("medium")
        if not meta.get("tumblr_url"): needed.append("tumblr")
        if not meta.get("github_pages_url"): needed.append("github_pages")
        if not meta.get("wp_link") and not meta.get("wp_post_id"): needed.append("wordpress")
        if not meta.get("blogger_url"): needed.append("blogger")
        
        # Social
        if not meta.get("x_post_id"): needed.append("x")
        if not meta.get("telegram_posted"): needed.append("telegram")
        if not meta.get("discord_posted"): needed.append("discord")
        if not meta.get("reddit_url"): needed.append("reddit")
        if not meta.get("pinterest_id"): needed.append("pinterest")
        if not meta.get("linkedin_id"): needed.append("linkedin")
        if not meta.get("youtube_shorts_id") and not meta.get("youtube_shorts_posted"): needed.append("youtube_shorts")
        if not meta.get("instagram_posted"): needed.append("instagram")
        if not meta.get("tiktok_posted"): needed.append("tiktok")
        
        return needed


    def _run_loop(self):
        lm = LedgerManager(Config.DATABASE_URL)
        self.log(f"Target Channels: {', '.join(BLOG_CHANNELS)}")
        
        while self.running:
            try:
                products = lm.get_all_products()
                promoted_count = 0
                
                for p in products:
                    if not self.running: break
                    
                    pid = p['id']
                    topic = p['topic']
                    needed_channels = self._get_unpromoted_blogs(pid, lm)
                    
                    if not needed_channels:
                        continue
                    
                    self.log(f"Checking {topic[:20]}... Needs: {needed_channels}")
                    
                    self.log(f"🚀 Promoting '{topic[:20]}' to {needed_channels}...")
                    results = dispatch_publish(pid, channels=needed_channels)
                    
                    # Log brief result
                    success = []
                    failed = []
                    dr = results.get("dispatch_results", {})
                    for ch, res in dr.items():
                        if res.get("ok"): success.append(ch)
                        else: failed.append(f"{ch}({res.get('error')})")
                    
                    if success: self.log(f"✅ Success: {', '.join(success)}")
                    if failed: self.log(f"❌ Failed: {', '.join(failed)}")
                    
                    promoted_count += 1
                    time.sleep(10)
            
                if not self.running: break
                
                if promoted_count == 0:
                    self.log("😴 No new promotions needed. Sleeping 60s...")
                    for _ in range(60):
                        if not self.running: break
                        time.sleep(1)
                else:
                    self.log(f"🎉 Batch done. Sleeping 30s...")
                    for _ in range(30):
                        if not self.running: break
                        time.sleep(1)
                        
            except Exception as e:
                self.log(f"⚠️ Error in bot loop: {e}")
                time.sleep(60)

# Global instance for easy import
bot_instance = BlogPromoBot()

if __name__ == "__main__":
    bot_instance.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        bot_instance.stop()
