import os
import sys
from src.medium_browser_client import MediumBrowserClient

def main():
    print("="*60)
    print(" MEDIUM AUTHENTICATION SETUP")
    print("="*60)
    print("Since Medium has stopped issuing new API tokens, we use a secure")
    print("browser automation method. This script will open a Chrome browser.")
    print("\nINSTRUCTIONS:")
    print("1. The browser will open to the Medium login page.")
    print("2. Log in using your preferred method (Google, Email, etc.).")
    print("3. Once you are logged in and see your homepage/avatar, CLOSE the browser window.")
    print("4. This will save your session cookies to 'chrome_profile' directory.")
    print("5. Future promotions will use this session to publish automatically.")
    print("="*60)
    
    input("\nPress Enter to launch browser...")
    
    try:
        # Initialize client (not headless for setup)
        client = MediumBrowserClient(headless=False)
        client.login_setup()
        
        # Verify if profile dir exists
        if os.path.exists("chrome_profile"):
            print("\n✅ Setup Complete! 'chrome_profile' directory created.")
            print("You can now run the promotion system.")
        else:
            print("\n⚠️ Warning: 'chrome_profile' directory not found. Something might have gone wrong.")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Make sure you have Chrome installed.")

if __name__ == "__main__":
    main()
