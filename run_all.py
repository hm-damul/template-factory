# -*- coding: utf-8 -*-
"""
run_all.py
운영자(사장님)를 위한 통합 실행 스크립트.
한 번의 실행으로 대시보드, 결제 서버, 프리뷰 서버를 모두 기동합니다.
"""

import os
import subprocess
import sys
import time
import socket
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
PYTHON_EXE = sys.executable

def is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        try:
            s.connect((host, port))
            return True
        except:
            return False

def start_process(name: str, cmd: list, log_name: str):
    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(exist_ok=True)
    log_path = logs_dir / log_name
    
    print(f"[INFO] Starting {name}...")
    f = open(log_path, "a", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        stdout=f,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        shell=False
    )
    return proc

def main():
    print("===============================================")
    print("   MetaPassiveIncome Unified Runner")
    print("===============================================")
    
    # 1. Dashboard (8099)
    if not is_port_open(8099):
        start_process("Dashboard", [PYTHON_EXE, "dashboard_server.py"], "dashboard_boot.log")
    else:
        print("[SKIP] Dashboard is already running on port 8099")

    # 2. Payment Server (5000)
    if not is_port_open(5000):
        start_process("Payment Server", [PYTHON_EXE, "backend/payment_server.py"], "payment_boot.log")
    else:
        print("[SKIP] Payment Server is already running on port 5000")

    # 3. Preview Server (8090)
    if not is_port_open(8090):
        start_process("Preview Server", [PYTHON_EXE, "preview_server.py"], "preview_boot.log")
    else:
        print("[SKIP] Preview Server is already running on port 8090")

    print("-----------------------------------------------")
    print("[WAIT] Waiting for servers to initialize...")
    
    # Dashboard가 뜰 때까지 대기
    for _ in range(10):
        if is_port_open(8099):
            print("[OK] Dashboard is ready!")
            break
        time.sleep(1)
    
    print("===============================================")
    print("All services are starting up.")
    print("- Dashboard: http://127.0.0.1:8099")
    print("- Preview:   http://127.0.0.1:8090/_list")
    print("- Payment:   http://127.0.0.1:5000/health")
    print("===============================================")
    
    # 브라우저 자동 오픈
    try:
        webbrowser.open("http://127.0.0.1:8099")
    except:
        pass

    print("\nPress Ctrl+C to exit (Servers will keep running in background).")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[INFO] Unified runner stopped. background processes may still be running.")

if __name__ == "__main__":
    main()
