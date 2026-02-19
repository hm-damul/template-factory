
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

def list_domains(project_name):
    token, team_id = get_config()
    headers = {"Authorization": f"Bearer {token}"}
    qs = f"?teamId={team_id}" if team_id else ""
    url = f"https://api.vercel.com/v9/projects/{project_name}/domains{qs}"
    
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        domains = r.json().get("domains", [])
        print(f"Found {len(domains)} domains:")
        for d in domains:
            print(f"Domain: {d.get('name')}")
    else:
        print(f"FAILED: {r.status_code} {r.text}")

if __name__ == "__main__":
    project_name = "meta-passive-income-20260213-081220-global-merchant-crypto-checkou"
    list_domains(project_name)
