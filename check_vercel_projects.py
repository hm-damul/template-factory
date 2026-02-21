import requests
import json

VERCEL_API_TOKEN = "YWxQGfmb3zJxW0uJTZi7gbVP"
HEADERS = {
    "Authorization": f"Bearer {VERCEL_API_TOKEN}",
    "Content-Type": "application/json"
}

def list_projects():
    url = "https://api.vercel.com/v9/projects?limit=20"
    try:
        r = requests.get(url, headers=HEADERS)
        if r.status_code == 200:
            data = r.json()
            projects = data.get("projects", [])
            print(f"Total Projects: {len(projects)}")
            for p in projects:
                print(f"- Name: {p['name']}")
                print(f"  URL: https://{p['name']}.vercel.app")
                if p.get("latestDeployments"):
                    deploy = p["latestDeployments"][0]
                    print(f"  ID: {deploy.get('uid') or deploy.get('id')}")
                    print(f"  Last Deploy: {deploy['url']}")
                    print(f"  Status: {deploy['readyState']}")
        else:
            print(f"Error: {r.status_code} {r.text}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    list_projects()
