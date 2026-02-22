import requests
import json

try:
    r = requests.get("https://dev-best-pick-global.pantheonsite.io/wp-json/wp/v2/posts/1370")
    if r.status_code == 200:
        content = r.json()['content']['rendered']
        print("--- POST CONTENT START ---")
        print(content)
        print("--- POST CONTENT END ---")
        
        if "metapassiveincome-final.vercel.app" in content:
            print("VERIFICATION: Vercel link found.")
        else:
            print("VERIFICATION: Vercel link NOT found.")
            
        if "127.0.0.1" in content or "localhost" in content:
            print("VERIFICATION: Localhost link found (BAD).")
        else:
             print("VERIFICATION: No localhost links found (GOOD).")
    else:
        print(f"Failed to fetch post: {r.status_code}")
except Exception as e:
    print(f"Error: {e}")
