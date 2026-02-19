import sys
import os
import requests
import base64
import time
from pathlib import Path

# 프로젝트 루트 추가
PROJECT_ROOT = Path(r"d:\auto\MetaPassiveIncome_FINAL")
sys.path.append(str(PROJECT_ROOT))

def test_wordpress_connection():
    wp_api_url = "https://dev-best-pick-global.pantheonsite.io/wp-json/wp/v2/posts"
    # secrets.json에서 읽어오기
    import json
    secrets_path = Path(r"d:\auto\MetaPassiveIncome_FINAL\data\secrets.json")
    with open(secrets_path, "r", encoding="utf-8") as f:
        secrets = json.load(f)
    
    wp_token = secrets.get("WP_TOKEN", "")
    
    print(f"Using WP_TOKEN: {wp_token}")
    
    if ":" in wp_token:
        import base64
        encoded_auth = base64.b64encode(wp_token.encode("utf-8")).decode("utf-8")
        headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/json",
        }
    else:
        headers = {
            "Authorization": f"Bearer {wp_token}",
            "Content-Type": "application/json",
        }
    
    # 먼저 게시글 목록 조회 시도 (읽기 권한 확인)
    print(f"Testing GET request to: {wp_api_url}?per_page=1")
    try:
        r_get = requests.get(f"{wp_api_url}?per_page=1", headers=headers, timeout=15)
        print(f"GET Status Code: {r_get.status_code}")
        if r_get.status_code == 200:
            print("SUCCESS: Read access verified.")
        else:
            print(f"FAILED: Read access failed. {r_get.text[:200]}")
    except Exception as e:
        print(f"GET Error: {e}")

    payload = {
        "title": "🚀 Digital Assets: Visual Preview & Payment Test (" + time.strftime("%Y-%m-%d %H:%M:%S") + ")",
        "content": """
        <h1>💰 Financial Freedom via Crypto Automation</h1>
        <p>If you're still relying on traditional income streams, you're missing out on the biggest wealth transfer in history.</p>
        
        <p>
            <a href="https://example.com/preview">
                <img src="https://images.unsplash.com/photo-1639762681485-074b7f938ba0?q=80&w=2000&auto=format&fit=crop" 
                     alt="Product Preview" 
                     style="max-width:100%; height:auto; border: 1px solid #ddd; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);" />
            </a>
            <br/>
            <em>*[Click the image above to view the live preview]*</em>
        </p>

        <h3>✅ Why Choose Our System?</h3>
        <ul>
            <li><strong>90% Support Reduction:</strong> Built-in troubleshooting matrices.</li>
            <li><strong>Deterministic Fulfillment:</strong> Instant delivery, no delays.</li>
            <li><strong>Privacy First:</strong> Crypto-native payments for maximum security.</li>
        </ul>
        
        <p>
            <a href="https://example.com/checkout">
                <img src="https://images.unsplash.com/photo-1556742044-3c52d6e88c62?q=80&w=2000&auto=format&fit=crop" 
                     alt="Secure Checkout" 
                     style="max-width:100%; height:auto; border: 1px solid #ddd; border-radius: 8px;" />
            </a>
        </p>

        <p>Join the 1% of digital entrepreneurs who are building scalable, passive income machines today.</p>
        <hr>
        <p><em>This is a verified system test from MetaPassiveIncome Pipeline with Visual Enhancements.</em></p>
        """,
        "status": "draft"
    }
    
    print(f"Connecting to: {wp_api_url}")
    try:
        r = requests.post(wp_api_url, headers=headers, json=payload, timeout=20)
        print(f"POST Status Code: {r.status_code}")
        print(f"Response: {r.text[:200]}...")
        if 200 <= r.status_code < 300:
            print("SUCCESS: WordPress connection verified (Create Post).")
            return True
        else:
            print("FAILED: Create Post failed.")
            return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    test_wordpress_connection()
