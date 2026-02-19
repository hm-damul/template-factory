
import os
import time
import random
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger("MediumBrowser")

class MediumBrowserClient:
    """
    Medium Browser Automation Client.
    Uses a persistent Chrome profile to maintain login session, bypassing API token requirements.
    """
    
    def __init__(self, profile_dir: str = "chrome_profile", headless: bool = False):
        self.profile_dir = os.path.abspath(profile_dir)
        self.headless = headless
        self.driver = None
        
    def _get_driver(self):
        if self.driver:
            return self.driver
            
        options = Options()
        # Essential: Persistent profile
        options.add_argument(f"user-data-dir={self.profile_dir}")
        
        # Anti-detection measures
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        if self.headless:
            options.add_argument("--headless=new")
            
        options.add_argument("--start-maximized")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        
        # Stealth patch
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })
        
        return self.driver

    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

    def login_setup(self):
        """
        Opens the browser for manual login. 
        Waits for the user to close the browser manually.
        """
        driver = self._get_driver()
        print("🚀 Opening Browser for Medium Login...")
        driver.get("https://medium.com/m/signin")
        
        print("\n" + "="*60)
        print(" ACTION REQUIRED: ")
        print(" 1. Please log in to Medium in the opened browser window.")
        print(" 2. Verify you are logged in (you should see your avatar).")
        print(" 3. CLOSE the browser window when done to save the session.")
        print("="*60 + "\n")
        
        try:
            # Loop until window is closed
            while True:
                time.sleep(1)
                # This will raise WebDriverException if window is closed
                _ = driver.current_url
        except Exception:
            print("✅ Browser closed. Session saved! You can now run automation.")
            self.driver = None  # Driver is already dead

    def create_post(self, title: str, content: str, tags: List[str] = None, publish_status: str = "draft") -> Dict[str, Any]:
        """
        Automates creating a story on Medium.
        
        Args:
            title: Story title
            content: Story content (Markdown or plain text - simple conversion applied)
            tags: List of tags (max 5)
            publish_status: 'public' or 'draft'. If 'draft', it just saves and exits.
        """
        driver = self._get_driver()
        wait = WebDriverWait(driver, 20)
        
        try:
            print("🚀 Navigating to New Story page...")
            driver.get("https://medium.com/new-story")
            
            # 1. Check if logged in (redirected to login page?)
            time.sleep(3)
            if "signin" in driver.current_url or "login" in driver.current_url:
                return {"success": False, "error": "Not logged in. Please run setup_medium_auth.py first."}

            # 2. Enter Title
            # Title field often is the first h3 or specific data-placeholder
            print("✍️ Entering Title...")
            title_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h3[data-testid='editorTitle']")))
            
            # Clear existing placeholders if any (click and type)
            title_field.click()
            time.sleep(0.5)
            # Send keys char by char for human-like behavior
            title_field.send_keys(title)
            time.sleep(1)

            # 3. Enter Content
            # Content is usually the p after h3
            print("✍️ Entering Content...")
            
            # Press enter from title to go to body
            title_field.send_keys(Keys.ENTER)
            time.sleep(1)
            
            active_elem = driver.switch_to.active_element
            
            # Split content by newlines
            paragraphs = content.split('\n')
            import re
            
            for p in paragraphs:
                if not p.strip():
                    continue
                

                # Handle Links: [text](url) -> text: url
                # Exposing the URL allows Medium to auto-link it, which is better for revenue/tracking
                p = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'\1: \2', p)
                
                # Handle Images: ![alt](url) -> Image: url
                p = re.sub(r'!\[([^\]]*)\]\(([^\)]+)\)', r'Image: \2', p)
                
                # Handle Headers
                if p.startswith('# '):
                    # Type '# ' to trigger H1
                    active_elem.send_keys('# ')
                    time.sleep(0.1)
                    active_elem.send_keys(p[2:])
                elif p.startswith('## '):
                    # Type '## ' to trigger H2
                    active_elem.send_keys('## ')
                    time.sleep(0.1)
                    active_elem.send_keys(p[3:])
                elif p.startswith('- '):
                    # Type '- ' to trigger List
                    active_elem.send_keys('- ')
                    time.sleep(0.1)
                    active_elem.send_keys(p[2:])
                elif p.startswith('> '):
                     # Type '> ' to trigger Quote
                    active_elem.send_keys('> ')
                    time.sleep(0.1)
                    active_elem.send_keys(p[2:])
                else:
                    active_elem.send_keys(p)
                
                # New paragraph
                active_elem.send_keys(Keys.ENTER)
                time.sleep(random.uniform(0.5, 1.5)) # Human-like typing delay (varied)
                active_elem = driver.switch_to.active_element # Re-capture

            time.sleep(3)

            # 4. Publish Flow
            print("🚀 Initiating Publish Flow...")
            # Click "Publish" button (top right green button)
            # Try multiple selectors as Medium changes them
            publish_btn = None
            try:
                publish_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='publishButton']")))
            except:
                try:
                    # Fallback by text
                    publish_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Publish')]")
                except:
                    print("❌ Could not find the initial Publish button.")
                    return {"success": False, "error": "Publish button not found"}

            publish_btn.click()
            
            time.sleep(2)
            
            # 5. Add Tags (in the modal/screen that appears)
            if tags:
                print(f"🏷️ Adding Tags: {tags}")
                try:
                    # Wait for tag input
                    tag_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='Add a topic...']")))
                    
                    for tag in tags[:5]: # Max 5 tags
                        tag_input.send_keys(tag)
                        time.sleep(random.uniform(0.5, 1.0))
                        tag_input.send_keys(Keys.ENTER) # Confirm tag
                        time.sleep(0.5)
                except Exception as e:
                    print(f"⚠️ Could not add tags: {e}")

            time.sleep(1)

            # 6. Final Confirm
            if publish_status == "public":
                print("🚀 Clicking Final Publish Now...")
                try:
                    final_publish_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-action='publish-doc']")))
                except:
                    # Fallback
                    final_publish_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Publish now')]")
                
                final_publish_btn.click()
                
                # Wait for redirect to story page
                wait.until(lambda d: "/new-story" not in d.current_url)
                story_url = driver.current_url
                print(f"✅ Published! URL: {story_url}")
                return {"success": True, "url": story_url, "status": "published"}
            else:
                print("💾 Saved as Draft (Publish skipped).")
                # To save as draft, we might just need to wait a bit as Medium auto-saves
                time.sleep(3) 
                return {"success": True, "status": "draft"}

        except Exception as e:
            logger.error(f"Failed to automate Medium: {e}")
            # Take screenshot for debugging
            try:
                driver.save_screenshot("medium_error.png")
            except:
                pass
            return {"success": False, "error": str(e)}
        finally:
            self.close()

if __name__ == "__main__":
    # Test run
    client = MediumBrowserClient(headless=False)
    client.login_setup()
