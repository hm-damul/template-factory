import requests
import sys

def check_url(url):
    try:
        resp = requests.get(url, timeout=2)
        print(f"{url}: {resp.status_code}")
        return True
    except Exception as e:
        print(f"{url}: Failed ({e})")
        return False

if __name__ == "__main__":
    with open("server_status.txt", "w") as f:
        d = check_url("http://127.0.0.1:8099/health")
        p = check_url("http://127.0.0.1:8088/health")
        pay = check_url("http://127.0.0.1:5000/health")
        
        if d:
            f.write("Dashboard is running\n")
        else:
            f.write("Dashboard is NOT running\n")
            
        if p:
            f.write("Preview is running\n")
        else:
            f.write("Preview is NOT running\n")
            
        if pay:
            f.write("Payment is running\n")
        else:
            f.write("Payment is NOT running\n")
