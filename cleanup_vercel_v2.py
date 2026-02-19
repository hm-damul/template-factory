# -*- coding: utf-8 -*-
import os
import requests
import time
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

VERCEL_TOKEN = os.getenv("VERCEL_API_TOKEN")

def cleanup_vercel():
    if not VERCEL_TOKEN:
        print("VERCEL_API_TOKEN not found.")
        return

    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    
    all_projects = []
    next_timestamp = None
    
    print("Fetching all projects (with pagination)...")
    while True:
        url = "https://api.vercel.com/v9/projects?limit=100"
        if next_timestamp:
            url += f"&until={next_timestamp}"
        
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Failed to fetch projects: {response.status_code}")
            break
            
        data = response.json()
        projects = data.get("projects", [])
        all_projects.extend(projects)
        
        pagination = data.get("pagination")
        if not pagination or not pagination.get("next"):
            break
        next_timestamp = pagination.get("next")
        
    print(f"Total projects found: {len(all_projects)}")
    
    # If we are near or over the limit (200), delete oldest ones
    if len(all_projects) >= 150:
        print("Cleaning up oldest 100 projects...")
        # Sort by creation date
        all_projects.sort(key=lambda x: x.get("createdAt", 0))
        
        to_delete = all_projects[:100]
        for p in to_delete:
            p_id = p.get("id")
            p_name = p.get("name")
            print(f"Deleting {p_name}...")
            del_url = f"https://api.vercel.com/v9/projects/{p_id}"
            del_resp = requests.delete(del_url, headers=headers)
            if del_resp.status_code == 204:
                print(f"Deleted {p_name}")
            else:
                print(f"Failed to delete {p_name}: {del_resp.status_code}")
            time.sleep(0.5) # Avoid hitting API rate limit
    else:
        print("Project count is safe.")

if __name__ == "__main__":
    cleanup_vercel()
