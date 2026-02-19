
import os
import requests
import json
from pathlib import Path

def get_config():
    # Try to load from Config or env
    token = os.getenv("VERCEL_API_TOKEN")
    team_id = os.getenv("VERCEL_ORG_ID") or os.getenv("VERCEL_TEAM_ID")
    
    # If not in env, try to read from secrets.json
    if not token:
        secrets_path = Path("data/secrets.json")
        if secrets_path.exists():
            data = json.loads(secrets_path.read_text(encoding="utf-8"))
            token = data.get("VERCEL_API_TOKEN")
            if not team_id:
                team_id = data.get("VERCEL_ORG_ID") or data.get("VERCEL_TEAM_ID")
    
    return token, team_id

def check_project(project_name):
    token, team_id = get_config()
    if not token:
        print("ERROR: VERCEL_API_TOKEN not found")
        return

    headers = {"Authorization": f"Bearer {token}"}
    qs = f"?teamId={team_id}" if team_id else ""
    url = f"https://api.vercel.com/v9/projects/{project_name}{qs}"
    
    print(f"Checking project: {project_name}")
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        data = r.json()
        print(f"Project found: {data.get('id')}")
        print("Full response data (keys):", data.keys())
        protection = data.get("protection")
        print(f"Protection settings: {json.dumps(protection, indent=2)}")
        
        # Check for other protection fields
        for k in data:
            if "protect" in k.lower() or "auth" in k.lower():
                print(f"Found {k}: {data[k]}")
    else:
        print(f"FAILED to get project: {r.status_code} {r.text}")

if __name__ == "__main__":
    # Get the latest project name from publisher or just try a known one
    # From redeploy logs: meta-passive-income-20260213-081220-global-merchant-crypto-checkou
    project_name = "meta-passive-income-20260213-081220-global-merchant-crypto-checkou"
    check_project(project_name)
