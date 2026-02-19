import requests
import os
import json

VERCEL_TOKEN = "e87M3f3Pqj76mK4U0m8S0x6u" # Config.py에서 가져오는 대신 직접 입력 (환경변수 확인용)

def get_deployment_status(deployment_url):
    # host 부분만 추출
    host = deployment_url.replace("https://", "").replace("/", "")
    
    url = f"https://api.vercel.com/v13/deployments/{host}"
    headers = {
        "Authorization": f"Bearer {VERCEL_TOKEN}",
    }
    
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        data = r.json()
        print(f"Deployment: {deployment_url}")
        print(f"Status: {data.get('status')}")
        print(f"Ready State: {data.get('readyState')}")
        if 'error' in data:
            print(f"Error: {data['error']}")
    else:
        print(f"Failed to get status for {deployment_url}: {r.status_code} {r.text}")

if __name__ == "__main__":
    urls = [
        "https://meta-passive-income-20260214-140141-ai-dev-income-5yua4ri64.vercel.app",
        "https://meta-passive-income-20260214-133737-ai-powered-passi-3h1y68b7r.vercel.app"
    ]
    for u in urls:
        get_deployment_status(u)
