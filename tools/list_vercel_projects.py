import os
import json
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
    pass

token = os.getenv("VERCEL_TOKEN") or os.getenv("VERCEL_API_TOKEN")
team_id = os.getenv("VERCEL_TEAM_ID") or os.getenv("VERCEL_ORG_ID")

if not token:
    print("No token found")
    exit(1)

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

url = "https://api.vercel.com/v9/projects"
if team_id:
    url += f"?teamId={team_id}"

try:
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        projects = r.json().get("projects", [])
        print(f"Found {len(projects)} projects:")
        for p in projects:
            print(f"- {p['name']} (ID: {p['id']})")
    else:
        print(f"Error: {r.status_code} {r.text}")
except Exception as e:
    print(f"Exception: {e}")
