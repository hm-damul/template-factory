import requests

url = "https://test-deploy-simple-public-na51tuwfp-dkkims-projects-a40a7241.vercel.app"
try:
    print(f"Checking {url}...")
    r = requests.get(url, timeout=10)
    print(f"Status Code: {r.status_code}")
    print(f"Content Length: {len(r.text)}")
    print(f"Title: {r.text[:500]}")
except Exception as e:
    print(f"Error: {e}")
