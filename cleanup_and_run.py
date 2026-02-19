
import os
import sys
import subprocess
import time
import signal

def kill_port(port):
    """Kills the process listening on the specified port on Windows."""
    try:
        # Find PID
        cmd = f"netstat -ano | findstr :{port}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        lines = result.stdout.strip().splitlines()
        pids = set()
        for line in lines:
            parts = line.split()
            if len(parts) >= 5:
                pid = parts[-1]
                if pid != "0":
                    pids.add(pid)
        
        for pid in pids:
            print(f"Killing PID {pid} on port {port}...")
            subprocess.run(f"taskkill /PID {pid} /F", shell=True)
            
    except Exception as e:
        print(f"Error killing port {port}: {e}")

def main():
    print("Cleaning up ports...")
    kill_port(5000)
    kill_port(8090)
    kill_port(8099)
    
    print("Ports cleaned.")
    
    # Run auto_mode_daemon.py
    print("Starting auto_mode_daemon.py...")
    # We use Popen to run it in background relative to this script, 
    # but we want it to persist. 
    # In this environment, we can just run it.
    subprocess.Popen([sys.executable, "auto_mode_daemon.py"], 
                     cwd=os.getcwd(),
                     creationflags=subprocess.CREATE_NEW_CONSOLE)
    print("Daemon started in new console.")

if __name__ == "__main__":
    main()
