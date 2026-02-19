import base64
import json
import os
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Load secrets from data/secrets.json
try:
    secrets_path = Path(__file__).resolve().parents[1] / "data" / "secrets.json"
    if secrets_path.exists():
        with open(secrets_path, "r", encoding="utf-8") as f:
            secrets = json.load(f)
            for k, v in secrets.items():
                if k not in os.environ and isinstance(v, str):
                    os.environ[k] = v
except Exception as e:
    print(f"Warning: Failed to load secrets.json: {e}")

def deploy_api():
    token = os.getenv("VERCEL_TOKEN") or os.getenv("VERCEL_API_TOKEN")
    if not token:
        print("Error: VERCEL_TOKEN or VERCEL_API_TOKEN not found in environment variables.")
        return

    # Files to include in deployment
    files_to_deploy = [
        "vercel.json",
        "requirements.txt",
        "order_store.py",
        "payment_api.py",
        "nowpayments_client.py",
        "evm_verifier.py",
        "api/main.py",
        "api/health.py",
        "api/__init__.py",
        "api/_vercel_common.py",
        "api/check.py", 
        "api/start.py", 
        "api/download.py",
        "outputs/test-prod-123/package.zip",
    ]

    project_root = Path(__file__).resolve().parents[1]
    
    # Collect file contents
    vercel_files = []
    print("Collecting files for deployment...")
    
    for rel_path in files_to_deploy:
        file_path = project_root / rel_path
        if file_path.exists():
            try:
                with open(file_path, "rb") as f:
                    content = f.read()
                vercel_files.append({
                    "file": rel_path,
                    "data": base64.b64encode(content).decode("utf-8"),
                    "encoding": "base64"
                })
                print(f"  - Added {rel_path}")
            except Exception as e:
                print(f"  - Failed to read {rel_path}: {e}")
        else:
            print(f"  - Warning: {rel_path} not found, skipping.")

    # API Payload
    payload = {
        "name": "meta-passive-income-20260215-212725-token-gated-content-revenue-au", 
        "project": "prj_5N2z94NQFOp85zbipIdk0fUBS34q",
        "files": vercel_files,
        "projectSettings": {"framework": None},
        "target": "production"
    }
    
    # Vercel API URL
    team_id = os.getenv("VERCEL_TEAM_ID", "").strip()
    qs = f"?teamId={team_id}" if team_id else ""
    url = f"https://api.vercel.com/v13/deployments{qs}"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    print("Deploying to Vercel...")
    try:
        r = requests.post(url, headers=headers, data=json.dumps(payload))
        if r.status_code >= 300:
            print(f"Deployment failed: {r.status_code}")
            print(r.text)
            return

        data = r.json()
        deployment_url = data.get("url")
        print(f"Deployment successful!")
        print(f"URL: https://{deployment_url}")
        
        # Check build status
        # id = data.get("id")
        # print(f"Deployment ID: {id}")
        
    except Exception as e:
        print(f"Error during deployment: {e}")

if __name__ == "__main__":
    deploy_api()
