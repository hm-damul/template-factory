# -*- coding: utf-8 -*-
import os
import requests
import json
from pathlib import Path
from dotenv import load_dotenv

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

VERCEL_TOKEN = os.getenv("VERCEL_API_TOKEN")

def check_and_cleanup_vercel():
    if not VERCEL_TOKEN:
        print("VERCEL_API_TOKEN not found in .env.")
        return

    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    
    # List projects
    url = "https://api.vercel.com/v9/projects"
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Failed to list projects: {response.status_code} {response.text}")
        return

    data = response.json()
    projects = data.get("projects", [])
    print(f"Current Vercel projects: {len(projects)}")
    
    if len(projects) >= 190:
        print("Approaching 200 project limit. Cleaning up oldest projects...")
        # Sort projects by creation date (oldest first)
        projects.sort(key=lambda x: x.get("createdAt", 0))
        
        # Delete oldest 50 projects to make enough room
        to_delete = projects[:50]
        for p in to_delete:
            p_id = p.get("id")
            p_name = p.get("name")
            print(f"Deleting project: {p_name} ({p_id})")
            del_url = f"https://api.vercel.com/v9/projects/{p_id}"
            del_resp = requests.delete(del_url, headers=headers)
            if del_resp.status_code == 204:
                print(f"Successfully deleted {p_name}")
            else:
                print(f"Failed to delete {p_name}: {del_resp.status_code}")
    else:
        print("Project count is safe.")

if __name__ == "__main__":
    check_and_cleanup_vercel()
