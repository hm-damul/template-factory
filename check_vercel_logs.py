import requests
import json

VERCEL_API_TOKEN = "YWxQGfmb3zJxW0uJTZi7gbVP"
HEADERS = {
    "Authorization": f"Bearer {VERCEL_API_TOKEN}",
    "Content-Type": "application/json"
}
DEPLOYMENT_ID = "dpl_DtNazXWzvu7pW2TBsKFNmuVBXNeD"

def get_logs():
    url = f"https://api.vercel.com/v2/deployments/{DEPLOYMENT_ID}/events"
    try:
        r = requests.get(url, headers=HEADERS)
        if r.status_code == 200:
            events = r.json()
            # print(json.dumps(events, indent=2))
            for e in events:
                text = e.get('text')
                if text:
                    print(text)
                payload = e.get('payload')
                if payload and payload.get('text'):
                    print(payload.get('text'))
        else:
            print(f"Error: {r.status_code} {r.text}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    get_logs()
