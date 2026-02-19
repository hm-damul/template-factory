import requests
import os
import json
from dotenv import load_dotenv

def check_actions():
    load_dotenv()
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        print("GITHUB_TOKEN not found.")
        return

    owner = "hm-damul"
    repo = "template-factory"
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        runs = res.json().get('workflow_runs', [])
        if not runs:
            print("No runs found.")
            return

        latest_run = runs[0]
        print(f"Latest Run ID: {latest_run['id']}")
        print(f"Status: {latest_run['status']}")
        print(f"Conclusion: {latest_run['conclusion']}")
        print(f"URL: {latest_run['html_url']}")
        
        # Get jobs status
        print("\n--- Jobs Status ---")
        jobs_url = latest_run['jobs_url']
        jobs_res = requests.get(jobs_url, headers=headers)
        jobs = jobs_res.json().get('jobs', [])
        for job in jobs:
            print(f"Job: {job['name']}, Conclusion: {job['conclusion']}")
            for step in job['steps']:
                print(f"  Step: {step['name']}, Status: {step['status']}, Conclusion: {step['conclusion']}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_actions()
