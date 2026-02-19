import json
import os
import sys
import webbrowser
import time
import logging
from pathlib import Path

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).parent
sys.path.append(str(PROJECT_ROOT))

from src.social_manager import SocialManager
try:
    from src.blog_manager import BlogManager
except ImportError:
    BlogManager = None

# Constants
SECRETS_PATH = PROJECT_ROOT / "data" / "secrets.json"
PROMO_CONFIG_PATH = PROJECT_ROOT / "data" / "promotion_config.json"
DATA_DIR = PROJECT_ROOT / "data"

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

# Try importing necessary libraries
try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    import requests
    from requests_oauthlib import OAuth1Session
    import tweepy
    import praw
    from moviepy.editor import ColorClip, TextClip, CompositeVideoClip
except ImportError as e:
    logging.info("Installing necessary libraries...")
    os.system(f"{sys.executable} -m pip install google-auth-oauthlib requests requests-oauthlib google-auth google-auth-httplib2 tweepy praw \"moviepy<2.0\"")
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        import requests
        from requests_oauthlib import OAuth1Session
        import tweepy
        import praw
        from moviepy.editor import ColorClip, TextClip, CompositeVideoClip
    except ImportError as e:
        logging.error(f"Failed to install libraries or import failed: {e}")
        print("Please check requirements.txt and run 'pip install -r requirements.txt' manually.")
        input("Press Enter to exit...")
        sys.exit(1)

def load_json(path):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except:
            return {}
    return {}

def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    logging.info(f"Saved configuration to {path.name}")

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header(title):
    print("\n" + "="*50)
    print(f" {title}")
    print("="*50 + "\n")

def check_status():
    secrets = load_json(SECRETS_PATH)
    print_header("Channel Configuration Status")
    
    channels = {
        "Blogger": ["BLOGGER_CLIENT_ID", "BLOGGER_CLIENT_SECRET", "BLOGGER_REFRESH_TOKEN", "BLOGGER_BLOG_ID"],
        "Tumblr": ["TUMBLR_CONSUMER_KEY", "TUMBLR_CONSUMER_SECRET", "TUMBLR_OAUTH_TOKEN", "TUMBLR_OAUTH_TOKEN_SECRET", "TUMBLR_BLOG_IDENTIFIER"],
        "Medium": ["MEDIUM_TOKEN", "MEDIUM_USER_ID"],
        "GitHub Pages": ["GITHUB_TOKEN", "GITHUB_REPO_URL", "GITHUB_USERNAME"],
        "Twitter/X": ["TWITTER_API_KEY", "TWITTER_API_SECRET", "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_TOKEN_SECRET"],
        "Reddit": ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USERNAME", "REDDIT_PASSWORD"],
        "Pinterest": ["PINTEREST_ACCESS_TOKEN", "PINTEREST_BOARD_ID"],
        "Telegram": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"],
        "Discord": ["DISCORD_WEBHOOK_URL"],
        "LinkedIn": ["LINKEDIN_ACCESS_TOKEN", "LINKEDIN_URN"],
        "YouTube": ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"]
    }
    
    for name, keys in channels.items():
        missing = [k for k in keys if not secrets.get(k)]
        status = "✅ Active" if not missing else "❌ Inactive"
        print(f"{name:<15} {status}")
        if missing:
            # Check for nested keys fallback (simple check)
            pass 

    print("\nTip: Select a channel from the menu to configure it.")
    input("\nPress Enter to return to menu...")

# --- Blogger Setup ---
def setup_blogger():
    print_header("Blogger (Google Blogspot) Setup")
    secrets = load_json(SECRETS_PATH)
    
    client_id = secrets.get("BLOGGER_CLIENT_ID")
    client_secret = secrets.get("BLOGGER_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        print("You need a Google Cloud Project with 'Blogger API' enabled.")
        print("1. Go to: https://console.cloud.google.com/apis/credentials")
        print("2. Create Credentials -> OAuth Client ID -> Application type: Desktop app")
        print("3. Enter Client ID and Secret below.")
        
        if input("Open Google Cloud Console? (y/n): ").lower() == 'y':
            webbrowser.open("https://console.cloud.google.com/apis/credentials")
        
        client_id = input("Enter Client ID: ").strip()
        client_secret = input("Enter Client Secret: ").strip()

    if not client_id or not client_secret:
        return

    secrets["BLOGGER_CLIENT_ID"] = client_id
    secrets["BLOGGER_CLIENT_SECRET"] = client_secret
    save_json(SECRETS_PATH, secrets)

    SCOPES = ['https://www.googleapis.com/auth/blogger']
    
    flow_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"]
        }
    }

    try:
        print("Launching browser for authentication...")
        flow = InstalledAppFlow.from_client_config(flow_config, SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True, access_type='offline', prompt='consent')
        
        if creds.refresh_token:
            secrets["BLOGGER_REFRESH_TOKEN"] = creds.refresh_token
            secrets["BLOGGER_ACCESS_TOKEN"] = creds.token
            
            # Ask for Blog ID
            print("\nTo find your Blog ID:")
            print("1. Go to your Blogger dashboard (https://www.blogger.com)")
            print("2. Look at the URL: https://www.blogger.com/blog/posts/BLOG_ID")
            print("3. Copy the number at the end.")
            
            if input("Open Blogger Dashboard? (y/n): ").lower() == 'y':
                webbrowser.open("https://www.blogger.com")

            blog_id = input("Enter Blog ID: ").strip()
            if blog_id:
                secrets["BLOGGER_BLOG_ID"] = blog_id

            save_json(SECRETS_PATH, secrets)
            print("Successfully authenticated!")
            
            # Test
            run_test("blogger")
        else:
            print("Warning: No refresh token returned.")
            
    except Exception as e:
        print(f"Error during Blogger auth: {e}")
        if "500" in str(e) or "redirect_uri_mismatch" in str(e) or "invalid_grant" in str(e):
             print("\nGoogle Auth Error detected. This usually happens if:")
             print("1. 'Authorized redirect URIs' in Google Console does not include http://localhost:8080/")
             print("2. The Client ID type is not 'Desktop app'.")
             print("3. You just created the credentials (wait 5 mins).")
             
             print("\nOptions:")
             print("1. Reset stored Client ID/Secret and try again")
             print("2. Skip Blogger setup for now")
             
             choice = input("Enter choice (1/2): ").strip()
             if choice == '1':
                 secrets.pop("BLOGGER_CLIENT_ID", None)
                 secrets.pop("BLOGGER_CLIENT_SECRET", None)
                 save_json(SECRETS_PATH, secrets)
                 print("Credentials cleared. Please restart setup.")
             else:
                 print("Skipping Blogger setup.")

# --- YouTube Setup ---
def setup_youtube():
    print_header("YouTube Shorts Setup")
    secrets = load_json(SECRETS_PATH)
    
    # Reuse Blogger client ID/Secret if available, or ask new
    client_id = secrets.get("YOUTUBE_CLIENT_ID") or secrets.get("BLOGGER_CLIENT_ID")
    client_secret = secrets.get("YOUTUBE_CLIENT_SECRET") or secrets.get("BLOGGER_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        print("You need a Google Cloud Project with 'YouTube Data API v3' enabled.")
        print("1. Go to: https://console.cloud.google.com/apis/credentials")
        print("2. Create Credentials -> OAuth Client ID -> Application type: Desktop app")
        
        if input("Open Google Cloud Console? (y/n): ").lower() == 'y':
            webbrowser.open("https://console.cloud.google.com/apis/credentials")
            
        client_id = input("Enter Client ID: ").strip()
        client_secret = input("Enter Client Secret: ").strip()

    if not client_id or not client_secret:
        return

    secrets["YOUTUBE_CLIENT_ID"] = client_id
    secrets["YOUTUBE_CLIENT_SECRET"] = client_secret
    save_json(SECRETS_PATH, secrets)

    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    
    flow_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"]
        }
    }

    try:
        print("Launching browser for authentication...")
        flow = InstalledAppFlow.from_client_config(flow_config, SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True, access_type='offline', prompt='consent')
        
        if creds.refresh_token:
            secrets["YOUTUBE_REFRESH_TOKEN"] = creds.refresh_token
            secrets["YOUTUBE_ACCESS_TOKEN"] = creds.token
            save_json(SECRETS_PATH, secrets)
            print("Successfully authenticated!")
            run_test("youtube")
        else:
            print("Warning: No refresh token returned.")
            
    except Exception as e:
        print(f"Error during YouTube auth: {e}")
        if "500" in str(e) or "redirect_uri_mismatch" in str(e) or "invalid_grant" in str(e):
             print("\nYouTube Auth Error detected. This usually happens if:")
             print("1. 'Authorized redirect URIs' in Google Console does not include http://localhost:8080/")
             print("2. The Client ID type is not 'Desktop app'.")
             
             print("\nOptions:")
             print("1. Reset stored Client ID/Secret and try again")
             print("2. Skip YouTube setup for now")
             
             choice = input("Enter choice (1/2): ").strip()
             if choice == '1':
                 secrets.pop("YOUTUBE_CLIENT_ID", None)
                 secrets.pop("YOUTUBE_CLIENT_SECRET", None)
                 # Also remove inherited blogger creds if they were used
                 if secrets.get("BLOGGER_CLIENT_ID") == secrets.get("YOUTUBE_CLIENT_ID"):
                     print("Note: YouTube was using Blogger credentials. Resetting Blogger credentials too.")
                     secrets.pop("BLOGGER_CLIENT_ID", None)
                     secrets.pop("BLOGGER_CLIENT_SECRET", None)
                 
                 save_json(SECRETS_PATH, secrets)
                 print("Credentials cleared. Please restart setup.")
             else:
                 print("Skipping YouTube setup.")


# --- Tumblr Setup ---
def setup_tumblr():
    print_header("Tumblr Setup")
    secrets = load_json(SECRETS_PATH)

    consumer_key = secrets.get("TUMBLR_CONSUMER_KEY") or input("Enter Tumblr Consumer Key: ").strip()
    consumer_secret = secrets.get("TUMBLR_CONSUMER_SECRET") or input("Enter Tumblr Consumer Secret: ").strip()
    
    if not consumer_key or not consumer_secret:
        print("Go to https://www.tumblr.com/oauth/apps to get keys.")
        if input("Open Tumblr OAuth Apps page? (y/n): ").lower() == 'y':
            webbrowser.open("https://www.tumblr.com/oauth/apps")
        return

    secrets["TUMBLR_CONSUMER_KEY"] = consumer_key
    secrets["TUMBLR_CONSUMER_SECRET"] = consumer_secret
    save_json(SECRETS_PATH, secrets)
    
    request_token_url = 'https://www.tumblr.com/oauth/request_token'
    authorization_base_url = 'https://www.tumblr.com/oauth/authorize'
    access_token_url = 'https://www.tumblr.com/oauth/access_token'

    try:
        oauth = OAuth1Session(consumer_key, client_secret=consumer_secret)
        fetch_response = oauth.fetch_request_token(request_token_url)
        resource_owner_key = fetch_response.get('oauth_token')
        resource_owner_secret = fetch_response.get('oauth_token_secret')
        
        authorization_url = oauth.authorization_url(authorization_base_url)
        print("\nPlease go here and authorize:", authorization_url)
        webbrowser.open(authorization_url)
        
        redirect_response = input("Paste the full redirect URL (or oauth_verifier) here: ").strip()
        
        oauth_verifier = None
        if "oauth_verifier=" in redirect_response:
            import urllib.parse
            parsed = urllib.parse.urlparse(redirect_response)
            qs = urllib.parse.parse_qs(parsed.query)
            oauth_verifier = qs['oauth_verifier'][0]
        else:
            oauth_verifier = redirect_response
            
        oauth = OAuth1Session(
            consumer_key,
            client_secret=consumer_secret,
            resource_owner_key=resource_owner_key,
            resource_owner_secret=resource_owner_secret,
            verifier=oauth_verifier
        )
        oauth_tokens = oauth.fetch_access_token(access_token_url)
        
        secrets["TUMBLR_OAUTH_TOKEN"] = oauth_tokens.get("oauth_token")
        secrets["TUMBLR_OAUTH_TOKEN_SECRET"] = oauth_tokens.get("oauth_token_secret")
        
        # Ask for Blog Identifier
        print("\nEnter your Tumblr Blog Identifier (e.g., myblog.tumblr.com):")
        blog_identifier = input("Blog Identifier: ").strip()
        if blog_identifier:
            secrets["TUMBLR_BLOG_IDENTIFIER"] = blog_identifier

        save_json(SECRETS_PATH, secrets)
        print("Tumblr setup complete!")
        
        # Test
        run_test("tumblr")
        
    except Exception as e:
        print(f"Error during Tumblr auth: {e}")

# --- Medium Setup ---
def setup_medium():
    print_header("Medium Setup")
    secrets = load_json(SECRETS_PATH)
    
    token = secrets.get("MEDIUM_TOKEN")
    if not token:
        print("Go to Settings -> Security and apps -> Integration tokens")
        if input("Open Medium Settings? (y/n): ").lower() == 'y':
            webbrowser.open("https://medium.com/me/settings/security")
        token = input("Enter Integration Token: ").strip()
    
    if token:
        secrets["MEDIUM_TOKEN"] = token
        
        # Fetch User ID automatically
        try:
            r = requests.get("https://api.medium.com/v1/me", headers={"Authorization": f"Bearer {token}"})
            if r.status_code == 200:
                user_data = r.json().get("data", {})
                user_id = user_data.get("id")
                username = user_data.get("username")
                print(f"Authenticated as: {username} ({user_id})")
                secrets["MEDIUM_USER_ID"] = user_id
            else:
                print("Failed to fetch user ID. Check token.")
        except Exception as e:
            print(f"Error fetching Medium User ID: {e}")

        save_json(SECRETS_PATH, secrets)
        run_test("medium")

# --- GitHub Pages Setup ---
def setup_github_pages():
    print_header("GitHub Pages Setup")
    secrets = load_json(SECRETS_PATH)
    
    print("Create a Personal Access Token with 'repo' scope.")
    if input("Open GitHub Settings? (y/n): ").lower() == 'y':
        webbrowser.open("https://github.com/settings/tokens")

    token = secrets.get("GITHUB_TOKEN") or input("Enter GitHub PAT: ").strip()
    repo = secrets.get("GITHUB_REPO_URL") or input("Enter Repository URL: ").strip()
    username = secrets.get("GITHUB_USERNAME") or input("Enter Username: ").strip()
    
    if token and repo and username:
        secrets["GITHUB_TOKEN"] = token
        secrets["GITHUB_REPO_URL"] = repo
        secrets["GITHUB_USERNAME"] = username
        save_json(SECRETS_PATH, secrets)
        print("GitHub Pages config saved.")
        run_test("github_pages")

# --- Twitter/X Setup ---
def setup_twitter():
    print_header("Twitter/X Setup")
    secrets = load_json(SECRETS_PATH)
    
    print("Go to https://developer.twitter.com/en/portal/dashboard to get keys.")
    if input("Open Twitter Developer Portal? (y/n): ").lower() == 'y':
        webbrowser.open("https://developer.twitter.com/en/portal/dashboard")

    api_key = secrets.get("TWITTER_API_KEY") or input("Enter API Key (Consumer Key): ").strip()
    api_secret = secrets.get("TWITTER_API_SECRET") or input("Enter API Secret (Consumer Secret): ").strip()
    access_token = secrets.get("TWITTER_ACCESS_TOKEN") or input("Enter Access Token: ").strip()
    access_token_secret = secrets.get("TWITTER_ACCESS_TOKEN_SECRET") or input("Enter Access Token Secret: ").strip()
    bearer_token = secrets.get("TWITTER_BEARER_TOKEN") or input("Enter Bearer Token (optional): ").strip()

    if api_key and api_secret and access_token and access_token_secret:
        secrets["TWITTER_API_KEY"] = api_key
        secrets["TWITTER_API_SECRET"] = api_secret
        secrets["TWITTER_ACCESS_TOKEN"] = access_token
        secrets["TWITTER_ACCESS_TOKEN_SECRET"] = access_token_secret
        if bearer_token:
            secrets["TWITTER_BEARER_TOKEN"] = bearer_token
        save_json(SECRETS_PATH, secrets)
        print("Twitter credentials saved.")
        
        run_test("twitter")

# --- Reddit Setup ---
def setup_reddit():
    print_header("Reddit Setup")
    secrets = load_json(SECRETS_PATH)
    
    print("Go to https://www.reddit.com/prefs/apps to create a 'script' app.")
    if input("Open Reddit Apps page? (y/n): ").lower() == 'y':
        webbrowser.open("https://www.reddit.com/prefs/apps")

    client_id = secrets.get("REDDIT_CLIENT_ID") or input("Enter Client ID: ").strip()
    client_secret = secrets.get("REDDIT_CLIENT_SECRET") or input("Enter Client Secret: ").strip()
    username = secrets.get("REDDIT_USERNAME") or input("Enter Reddit Username: ").strip()
    password = secrets.get("REDDIT_PASSWORD") or input("Enter Reddit Password: ").strip()
    
    if client_id and client_secret and username and password:
        secrets["REDDIT_CLIENT_ID"] = client_id
        secrets["REDDIT_CLIENT_SECRET"] = client_secret
        secrets["REDDIT_USERNAME"] = username
        secrets["REDDIT_PASSWORD"] = password
        save_json(SECRETS_PATH, secrets)
        print("Reddit credentials saved.")
        
        run_test("reddit")

# --- Pinterest Setup ---
def setup_pinterest():
    print_header("Pinterest Setup")
    secrets = load_json(SECRETS_PATH)
    
    print("You need a Pinterest Access Token (v5).")
    print("Go to Pinterest Developer Portal -> Tools -> API Explorer to generate a token.")
    if input("Open Pinterest Developer Tools? (y/n): ").lower() == 'y':
        webbrowser.open("https://developers.pinterest.com/tools/api-explorer/")

    token = secrets.get("PINTEREST_ACCESS_TOKEN") or input("Enter Access Token: ").strip()
    board_id = secrets.get("PINTEREST_BOARD_ID") or input("Enter Board ID to pin to: ").strip()
    
    if token and board_id:
        secrets["PINTEREST_ACCESS_TOKEN"] = token
        secrets["PINTEREST_BOARD_ID"] = board_id
        save_json(SECRETS_PATH, secrets)
        print("Pinterest credentials saved.")
        run_test("pinterest")

# --- Telegram Setup ---
def setup_telegram():
    print_header("Telegram Setup")
    secrets = load_json(SECRETS_PATH)
    
    print("Create a bot with @BotFather to get a token.")
    if input("Open Telegram Web? (y/n): ").lower() == 'y':
        webbrowser.open("https://web.telegram.org/")

    token = secrets.get("TELEGRAM_BOT_TOKEN") or input("Enter Bot Token: ").strip()
    chat_id = secrets.get("TELEGRAM_CHAT_ID") or input("Enter Channel/Chat ID (e.g. @channelname or -100...): ").strip()
    
    if token and chat_id:
        secrets["TELEGRAM_BOT_TOKEN"] = token
        secrets["TELEGRAM_CHAT_ID"] = chat_id
        save_json(SECRETS_PATH, secrets)
        print("Telegram credentials saved.")
        run_test("telegram")

# --- Discord Setup ---
def setup_discord():
    print_header("Discord Setup")
    secrets = load_json(SECRETS_PATH)
    
    print("Go to Server Settings -> Integrations -> Webhooks")
    webhook = secrets.get("DISCORD_WEBHOOK_URL") or input("Enter Webhook URL: ").strip()
    
    if webhook:
        secrets["DISCORD_WEBHOOK_URL"] = webhook
        save_json(SECRETS_PATH, secrets)
        print("Discord webhook saved.")
        run_test("discord")

# --- LinkedIn Setup ---
def setup_linkedin():
    print_header("LinkedIn Setup")
    secrets = load_json(SECRETS_PATH)
    
    print("Requires OAuth Access Token and Person URN.")
    print("Go to LinkedIn Developer Portal -> My Apps -> Auth to generate token.")
    if input("Open LinkedIn Developer Portal? (y/n): ").lower() == 'y':
        webbrowser.open("https://www.linkedin.com/developers/apps/")

    token = secrets.get("LINKEDIN_ACCESS_TOKEN") or input("Enter Access Token: ").strip()
    urn = secrets.get("LINKEDIN_URN") or input("Enter URN (e.g., urn:li:person:12345): ").strip()
    
    if token and urn:
        secrets["LINKEDIN_ACCESS_TOKEN"] = token
        secrets["LINKEDIN_URN"] = urn
        save_json(SECRETS_PATH, secrets)
        print("LinkedIn credentials saved.")
        run_test("linkedin")

def create_dummy_video(filename="test_video.mp4"):
    """Creates a simple dummy video for testing using moviepy."""
    try:
        from moviepy.editor import ColorClip, TextClip, CompositeVideoClip
        # Create a red background
        clip = ColorClip(size=(720, 1280), color=(255, 0, 0), duration=5)
        # TextClip might fail if ImageMagick is not installed, so we wrap it
        try:
            txt_clip = TextClip("Test Video", fontsize=70, color='white').set_pos('center').set_duration(5)
            video = CompositeVideoClip([clip, txt_clip])
        except:
            print("ImageMagick not found, creating simple color video.")
            video = clip
            
        video.write_videofile(filename, fps=24, codec='libx264', audio=False, verbose=False, logger=None)
        return True
    except Exception as e:
        print(f"Failed to create dummy video: {e}")
        return False

def run_test(channel):
    """Run a quick test post for the configured channel."""
    print(f"\n--- Testing {channel} ---")
    confirm = input(f"Do you want to send a test post to {channel}? (y/n): ").strip().lower()
    if confirm != 'y':
        return

    sm = SocialManager(config_path=PROMO_CONFIG_PATH, secrets_path=SECRETS_PATH)
    res = {}
    
    test_msg = f"Test post from MetaPassiveIncome setup at {time.strftime('%Y-%m-%d %H:%M:%S')}"
    
    try:
        if channel == "twitter":
            res = sm.post_to_twitter(test_msg)
        elif channel == "reddit":
            # Default to user profile if subreddit not set
            subreddit = sm.secrets.get('REDDIT_USERNAME')
            if subreddit:
                subreddit = f"u_{subreddit}"
            else:
                subreddit = "test"
            res = sm.post_to_reddit(title="Test Post", url="https://google.com", subreddit_name=subreddit)
        elif channel == "pinterest":
            res = sm.post_to_pinterest(
                title="Test Pin", 
                description=test_msg, 
                link="https://google.com", 
                image_url="https://picsum.photos/200/300"
            )
        elif channel == "telegram":
            res = sm.post_to_telegram(test_msg)
        elif channel == "discord":
            res = sm.post_to_discord(test_msg)
        elif channel == "linkedin":
            res = sm.post_to_linkedin(test_msg, "https://google.com")
        elif channel == "youtube":
            print("Creating dummy video for upload test...")
            video_file = "test_short.mp4"
            if create_dummy_video(video_file):
                res = sm.post_to_youtube(
                    title="Test Short", 
                    description=test_msg, 
                    video_path=video_file
                )
                # Cleanup
                try:
                    os.remove(video_file)
                except: pass
            else:
                res = {"ok": False, "msg": "Could not create video file"}
        
        # Blog channels
        elif channel == "blogger":
            bm = BlogManager(blogger_creds={
                "client_id": sm.secrets.get("BLOGGER_CLIENT_ID"),
                "client_secret": sm.secrets.get("BLOGGER_CLIENT_SECRET"),
                "refresh_token": sm.secrets.get("BLOGGER_REFRESH_TOKEN"),
                "blog_id": sm.secrets.get("BLOGGER_BLOG_ID")
            })
            url = bm.publish_blogger(
                blog_id=sm.secrets.get("BLOGGER_BLOG_ID"),
                title="Test Post",
                content=f"<p>{test_msg}</p>",
                tags=["test"]
            )
            res = {"ok": bool(url), "url": url}

        elif channel == "tumblr":
            bm = BlogManager(tumblr_creds={
                "consumer_key": sm.secrets.get("TUMBLR_CONSUMER_KEY"),
                "consumer_secret": sm.secrets.get("TUMBLR_CONSUMER_SECRET"),
                "oauth_token": sm.secrets.get("TUMBLR_OAUTH_TOKEN"),
                "oauth_token_secret": sm.secrets.get("TUMBLR_OAUTH_TOKEN_SECRET")
            })
            url = bm.publish_tumblr(
                blog_identifier=sm.secrets.get("TUMBLR_BLOG_IDENTIFIER"),
                title="Test Post",
                content=f"{test_msg}",
                tags=["test"]
            )
            res = {"ok": bool(url), "url": url}

        elif channel == "medium":
            bm = BlogManager(medium_token=sm.secrets.get("MEDIUM_TOKEN"))
            url = bm.publish_medium(
                title="Test Post",
                content=f"{test_msg}",
                tags=["test"]
            )
            res = {"ok": bool(url), "url": url}
            
        elif channel == "github_pages":
            bm = BlogManager(github_creds={
                "username": sm.secrets.get("GITHUB_USERNAME"),
                "token": sm.secrets.get("GITHUB_TOKEN"),
                "repo_url": sm.secrets.get("GITHUB_REPO_URL")
            })
            url = bm.publish_github_pages(
                repo_url=sm.secrets.get("GITHUB_REPO_URL"),
                title="Test Post",
                content=f"{test_msg}",
                filename="test-post.md"
            )
            res = {"ok": bool(url), "url": url}

    except Exception as e:
        res = {"ok": False, "msg": str(e)}
        print(f"Error: {e}")

    if res.get("ok"):
        print(f"✅ Test successful! URL/ID: {res.get('url') or res.get('id')}")
    else:
        print(f"❌ Test failed: {res.get('msg')}")
    
    input("Press Enter to continue...")

def auto_setup_all():
    print_header("Auto Setup Sequence")
    print("This will guide you through all channels sequentially.")
    print("If you don't have keys for a channel, you can skip it.")
    
    channels = [
        ("Blogger", setup_blogger),
        ("Tumblr", setup_tumblr),
        ("Medium", setup_medium),
        ("GitHub Pages", setup_github_pages),
        ("Twitter/X", setup_twitter),
        ("Reddit", setup_reddit),
        ("Pinterest", setup_pinterest),
        ("Telegram", setup_telegram),
        ("Discord", setup_discord),
        ("LinkedIn", setup_linkedin),
        ("YouTube Shorts", setup_youtube)
    ]
    
    for name, func in channels:
        print(f"\n>>> Starting setup for: {name}")
        try:
            func()
        except Exception as e:
            print(f"Error setting up {name}: {e}")
        
        print(f"\nFinished {name}. Moving to next...")
        time.sleep(1)
    
    print("\nAll channels processed!")
    input("Press Enter to return to menu...")

def main():
    while True:
        clear_screen()
        print_header("MetaPassiveIncome Setup & Dashboard")
        
        check_status()
        
        print("Select a channel to configure:")
        print("00. AUTO SETUP ALL CHANNELS (Recommended)")
        print("1. Blogger (Google)")
        print("2. Tumblr")
        print("3. Medium")
        print("4. GitHub Pages")
        print("5. Twitter/X")
        print("6. Reddit")
        print("7. Pinterest")
        print("8. Telegram")
        print("9. Discord")
        print("10. LinkedIn")
        print("11. YouTube Shorts")
        print("0. Exit")
        
        choice = input("\nEnter choice: ").strip()
        
        if choice == '00': auto_setup_all()
        elif choice == '1': setup_blogger()
        elif choice == '2': setup_tumblr()
        elif choice == '3': setup_medium()
        elif choice == '4': setup_github_pages()
        elif choice == '5': setup_twitter()
        elif choice == '6': setup_reddit()
        elif choice == '7': setup_pinterest()
        elif choice == '8': setup_telegram()
        elif choice == '9': setup_discord()
        elif choice == '10': setup_linkedin()
        elif choice == '11': setup_youtube()
        elif choice == '0': break
        else:
            print("Invalid choice.")
            time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FATAL ERROR in Interactive Setup: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")
        sys.exit(1)

