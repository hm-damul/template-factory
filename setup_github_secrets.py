import os
import json
import base64
import requests
from nacl import encoding, public
from dotenv import load_dotenv

def encrypt(public_key: str, secret_value: str) -> str:
    """Encrypt a Unicode string using the public key."""
    public_key = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")

def set_github_secret(owner, repo, token, secret_name, secret_value):
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    
    # 1. Get public key
    pub_key_url = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/public-key"
    res = requests.get(pub_key_url, headers=headers)
    if res.status_code != 200:
        print(f"Error getting public key for {secret_name}: {res.status_code} {res.text}")
        return False
    
    pub_key_data = res.json()
    key_id = pub_key_data["key_id"]
    public_key = pub_key_data["key"]
    
    # 2. Encrypt secret
    encrypted_value = encrypt(public_key, secret_value)
    
    # 3. Put secret
    secret_url = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/{secret_name}"
    data = {
        "encrypted_value": encrypted_value,
        "key_id": key_id,
    }
    res = requests.put(secret_url, headers=headers, json=data)
    
    if res.status_code in [201, 204]:
        print(f"Successfully set secret: {secret_name}")
        return True
    else:
        print(f"Error setting secret {secret_name}: {res.status_code} {res.text}")
        return False

def main():
    load_dotenv()
    
    owner = "hm-damul"
    repo = "template-factory"
    token = os.getenv("GITHUB_TOKEN")
    
    if not token:
        print("GITHUB_TOKEN not found in .env")
        return

    # Secrets mapping: (GitHub Secret Name, Env Var Name)
    secrets_to_set = [
        ("VERCEL_API_TOKEN", "VERCEL_API_TOKEN"),
        ("UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_URL"),
        ("UPSTASH_REDIS_REST_TOKEN", "UPSTASH_REDIS_REST_TOKEN"),
        ("NOWPAYMENTS_API_KEY", "NOWPAYMENTS_API_KEY"),
        ("MERCHANT_WALLET_ADDRESS", "MERCHANT_WALLET_ADDRESS"),
        ("DOWNLOAD_TOKEN_SECRET", "DOWNLOAD_TOKEN_SECRET"),
        # GEMINI_API_KEY is missing, but we'll try to set it if it exists
        ("GEMINI_API_KEY", "GEMINI_API_KEY"),
        # X (Twitter) API Keys
        ("X_CONSUMER_KEY", "X_CONSUMER_KEY"),
        ("X_CONSUMER_SECRET", "X_CONSUMER_SECRET"),
        ("X_ACCESS_TOKEN", "X_ACCESS_TOKEN"),
        ("X_ACCESS_TOKEN_SECRET", "X_ACCESS_TOKEN_SECRET"),
        ("X_BEARER_TOKEN", "X_BEARER_TOKEN"),
    ]
    
    # Also check data/secrets.json
    secrets_json_path = "data/secrets.json"
    secrets_json = {}
    if os.path.exists(secrets_json_path):
        with open(secrets_json_path, "r") as f:
            secrets_json = json.load(f)

    for gh_name, env_name in secrets_to_set:
        val = os.getenv(env_name) or secrets_json.get(env_name)
        if val:
            set_github_secret(owner, repo, token, gh_name, val)
        else:
            print(f"Skipping {gh_name}: Value not found in .env or secrets.json")

if __name__ == "__main__":
    main()
