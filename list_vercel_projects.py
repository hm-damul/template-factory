
import requests
import json
import os

def list_projects():
    api_token = "YWxQGfmb3zJxW0uJTZi7gbVP"
    team_id = "team_9D4f6AisHAKYHEIscezhpefx"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    url = f"https://api.vercel.com/v9/projects?teamId={team_id}"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        projects = r.json().get("projects", [])
        for p in projects:
            print(f"Name: {p['name']}, ID: {p['id']}")
    else:
        print(f"Error: {r.status_code} {r.text}")

if __name__ == "__main__":
    list_projects()
