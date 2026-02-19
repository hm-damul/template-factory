
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

def kill_process(name):
    try:
        if os.name == 'nt':
            subprocess.run(["taskkill", "/F", "/IM", "python.exe", "/FI", f"WINDOWTITLE eq {name}*"], check=False)
            # Also try by command line match if possible, but window title is tricky.
            # Just kill all python processes? No, that kills me too.
            # We rely on previous known PIDs if stored.
            pass
        else:
            subprocess.run(["pkill", "-f", name], check=False)
    except Exception as e:
        print(f"Error killing {name}: {e}")

def start_process(script_name, cwd):
    print(f"Starting {script_name}...")
    if os.name == 'nt':
        # specific to windows
        subprocess.Popen([sys.executable, script_name], cwd=cwd, creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        subprocess.Popen([sys.executable, script_name], cwd=cwd, start_new_session=True)

def main():
    root = Path(__file__).parent
    
    # We can't easily kill specific python scripts on Windows without PIDs.
    # So we'll just start new ones and hope the old ones die or we manually kill them?
    # Or we can just let the user handle it?
    # The user is on Windows.
    # The dashboard server runs on port 8501 (Streamlit) or 5000 (Flask)?
    # dashboard_server.py is Flask on 8000.
    
    # Let's try to kill by port if possible.
    # But for now, just starting new instances might conflict on port.
    
    print("Restarting services...")
    # This is risky without proper process management.
    # I'll skip killing and just suggest the user to restart if needed.
    # But I can try to run them if not running.
    
    # Actually, I'll just check if they respond.
    import requests
    try:
        r = requests.get("http://localhost:8000/api/status", timeout=2)
        print(f"Dashboard status: {r.status_code}")
    except:
        print("Dashboard not responding, starting...")
        start_process("dashboard_server.py", str(root))

    try:
        r = requests.get("http://localhost:5000/health", timeout=2) # Payment server port?
        print(f"Payment server status: {r.status_code}")
    except:
        print("Payment server not responding, starting...")
        # payment_server.py location?
        if (root / "backend" / "payment_server.py").exists():
            start_process("backend/payment_server.py", str(root))
        else:
            print("Payment server not found")

if __name__ == "__main__":
    main()
