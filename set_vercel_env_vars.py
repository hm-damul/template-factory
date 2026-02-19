
import requests
import json
import os

def set_vercel_env():
    api_token = "YWxQGfmb3zJxW0uJTZi7gbVP"
    team_id = "team_9D4f6AisHAKYHEIscezhpefx"
    nowpayments_key = "ww-88314aa6-9392-40fd-a6d0-aefc8eb88523-widgetOnLoad"
    
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    
    # 1. Get projects
    url = f"https://api.vercel.com/v9/projects?teamId={team_id}"
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        print(f"Failed to list projects: {r.text}")
        return
    
    projects = r.json().get("projects", [])
    print(f"Found {len(projects)} projects.")
    
    for p in projects:
        project_id = p['id']
        project_name = p['name']
        
        # Env vars to set
        env_vars = {
            "NOWPAYMENTS_API_KEY": nowpayments_key,
            "PAYMENT_MODE": "nowpayments"
        }
        
        # 2. Get current envs
        env_url = f"https://api.vercel.com/v9/projects/{project_id}/env?teamId={team_id}"
        er = requests.get(env_url, headers=headers)
        envs = er.json().get("envs", [])
        
        for key, value in env_vars.items():
            existing_env = next((e for e in envs if e['key'] == key), None)
            
            if existing_env:
                # Update
                env_id = existing_env['id']
                update_url = f"https://api.vercel.com/v9/projects/{project_id}/env/{env_id}?teamId={team_id}"
                payload = {
                    "value": value,
                    "target": ["production", "preview", "development"]
                }
                ur = requests.patch(update_url, headers=headers, json=payload)
                if ur.status_code == 200:
                    print(f"Updated {key} for {project_name}")
                else:
                    print(f"Failed to update {key} for {project_name}: {ur.text}")
            else:
                # Create
                payload = {
                    "key": key,
                    "value": value,
                    "type": "encrypted",
                    "target": ["production", "preview", "development"]
                }
                cr = requests.post(env_url, headers=headers, json=payload)
                if cr.status_code == 200:
                    print(f"Created {key} for {project_name}")
                else:
                    print(f"Failed to create {key} for {project_name}: {cr.text}")

if __name__ == "__main__":
    set_vercel_env()
