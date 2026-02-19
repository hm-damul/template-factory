import requests
import os
import zipfile
import io
from dotenv import load_dotenv

def get_run_logs(run_id):
    load_dotenv()
    token = os.getenv('GITHUB_TOKEN')
    owner = "hm-damul"
    repo = "template-factory"
    
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/logs"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        
        # Logs are returned as a zip file
        with zipfile.ZipFile(io.BytesIO(res.content)) as z:
            for filename in z.namelist():
                if "Run Auto Batch" in filename:
                    with z.open(filename) as f:
                        print(f"--- Logs from {filename} ---")
                        print(f.read().decode('utf-8')[-2000:]) # Show last 2000 chars
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    import sys
    run_id = sys.argv[1] if len(sys.argv) > 1 else "21980260202"
    get_run_logs(run_id)
