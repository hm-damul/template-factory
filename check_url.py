import requests

def check_url(url):
    print(f"Checking {url}...")
    try:
        r = requests.head(url, allow_redirects=True)
        print(f"Status: {r.status_code}")
        if r.status_code != 200:
             print(f"GETting...")
             r = requests.get(url, allow_redirects=True)
             print(f"GET Status: {r.status_code}")
             if r.status_code == 200:
                 print(f"Content-Length: {len(r.content)}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    base = "https://metapassiveincome-final.vercel.app"
    paths = [
        "/",
        "/index.html",
        "/featured.html",
        "/api/health"
    ]
    for p in paths:
        check_url(base + p)
