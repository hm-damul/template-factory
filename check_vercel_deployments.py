import requests
import json
import os
from pathlib import Path

# Load secrets
secrets_path = Path("data/secrets.json")
if secrets_path.exists():
    secrets = json.loads(secrets_path.read_text(encoding="utf-8"))
    token = secrets.get("VERCEL_API_TOKEN")
else:
    print("Secrets file not found.")
    exit(1)

if not token:
    print("Vercel token not found.")
    exit(1)

project_name = "metapassiveincome-final"
url = f"https://api.vercel.com/v6/deployments?projectId={project_name}&limit=5"
headers = {"Authorization": f"Bearer {token}"}

try:
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        deployments = response.json().get("deployments", [])
        print(f"Recent deployments for {project_name}:")
        for dep in deployments:
            print(f"ID: {dep['uid']}")
            print(f"State: {dep['state']}")
            print(f"Created: {dep['created']}")
            print(f"URL: {dep['url']}")
            print(f"Commit: {dep.get('meta', {}).get('githubCommitMessage', 'N/A')}")
            print("-" * 30)
    else:
        print(f"Error fetching deployments: {response.status_code} - {response.text}")
        
        # Try finding project ID first if project name fails in query (sometimes needed)
        # But projectId query param usually works with name or ID.
except Exception as e:
    print(f"Exception: {e}")
