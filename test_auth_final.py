import requests
import base64

def try_auth_variants_new_pass():
    password = "ftEF iIyx T6XD Xo8K gZmm lNAm"
    variants = ["admin", "best-pick-global", "live-best-pick-global"]
    
    url = "https://live-best-pick-global.pantheonsite.io/wp-json/wp/v2/posts"
    
    for user in variants:
        auth_str = f"{user}:{password}"
        encoded = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
        headers = {"Authorization": f"Basic {encoded}"}
        
        print(f"Testing User: {user}")
        try:
            # Try a POST to check write permission (draft)
            payload = {"title": "Auth Test", "content": "test", "status": "draft"}
            r = requests.post(url, headers=headers, json=payload, timeout=10)
            print(f"  POST Status: {r.status_code}")
            if r.status_code == 201:
                print(f"  SUCCESS! User '{user}' has POST permission.")
                return user
        except Exception as e:
            print(f"  Error: {e}")
            
    return None

if __name__ == "__main__":
    try_auth_variants_new_pass()
