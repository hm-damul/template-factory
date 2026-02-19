
import os
import requests
import json
from pathlib import Path

def get_config():
    token = os.getenv("VERCEL_API_TOKEN")
    team_id = os.getenv("VERCEL_ORG_ID") or os.getenv("VERCEL_TEAM_ID")
    if not token:
        secrets_path = Path("data/secrets.json")
        if secrets_path.exists():
            data = json.loads(secrets_path.read_text(encoding="utf-8"))
            token = data.get("VERCEL_API_TOKEN")
            if not team_id:
                team_id = data.get("VERCEL_ORG_ID") or data.get("VERCEL_TEAM_ID")
    return token, team_id

def get_latest_deployment_logs(project_name):
    token, team_id = get_config()
    headers = {"Authorization": f"Bearer {token}"}
    qs = f"?teamId={team_id}" if team_id else ""
    
    # 1. Get project ID
    url = f"https://api.vercel.com/v9/projects/{project_name}{qs}"
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        print(f"FAILED to get project: {r.status_code} {r.text}")
        return
    project_id = r.json().get("id")
    
    # 2. Get latest deployment
    url = f"https://api.vercel.com/v6/deployments{qs}&projectId={project_id}&limit=1"
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        print(f"FAILED to get deployments: {r.status_code} {r.text}")
        return
    deployments = r.json().get("deployments", [])
    if not deployments:
        print("No deployments found.")
        return
    
    deployment = deployments[0]
    deployment_id = deployment.get("uid")
    print(f"Latest Deployment: {deployment_id} ({deployment.get('url')}) status: {deployment.get('status')}")
    
    # 3. Get events (logs)
    url = f"https://api.vercel.com/v3/deployments/{deployment_id}/events{qs}"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        events = r.json()
        print(f"Found {len(events)} log events:")
        for ev in events:
            text = ev.get("text", "")
            if text:
                print(f"[{ev.get('type')}] {text}")
    else:
        print(f"FAILED to get logs: {r.status_code} {r.text}")

if __name__ == "__main__":
    project_name = "meta-passive-income-20260213-081220-global-merchant-crypto-checkou"
    get_latest_deployment_logs(project_name)
