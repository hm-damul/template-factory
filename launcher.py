import os
import sys
import time
import subprocess
import socket
import logging
from pathlib import Path
import threading

# 설정
PROJECT_ROOT = Path(__file__).parent.absolute()
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [LAUNCHER] - %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "system_launcher.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("SystemLauncher")

def is_port_open(host, port):
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except:
        return False

class ServiceManager:
    def __init__(self, name, command, port=None, cwd=None):
        self.name = name
        self.command = command
        self.port = port
        self.cwd = cwd or PROJECT_ROOT
        self.process = None
        self.restart_count = 0

    def start(self):
        if self.port and is_port_open("127.0.0.1", self.port):
            logger.info(f"✅ {self.name} is already running on port {self.port}")
            # 이미 실행 중인 경우 프로세스 핸들이 없으므로 restart_count 등을 관리하지 않음
            # 단, 이 경우 런처가 종료되면 좀비가 될 수 있음
            return

        logger.info(f"🚀 Starting {self.name}...")
        try:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            
            # 로그 파일 열기
            stdout_log = open(LOGS_DIR / f"{self.name}.out.log", "a", encoding="utf-8")
            stderr_log = open(LOGS_DIR / f"{self.name}.err.log", "a", encoding="utf-8")

            self.process = subprocess.Popen(
                self.command,
                cwd=str(self.cwd),
                stdout=stdout_log,
                stderr=stderr_log,
                shell=False,
                env=env
            )
            logger.info(f"✅ {self.name} started (PID: {self.process.pid})")
        except Exception as e:
            logger.error(f"❌ Failed to start {self.name}: {e}")

    def is_running(self):
        # 포트 기반 체크 우선
        if self.port:
            if is_port_open("127.0.0.1", self.port):
                return True
            # 포트가 닫혀있으면 프로세스도 죽은 것으로 간주
            return False
        
        # 포트 없는 프로세스(데몬)는 핸들 체크
        if self.process:
            return self.process.poll() is None
        return False

    def monitor(self):
        if not self.is_running():
            logger.warning(f"⚠️ {self.name} is down. Restarting...")
            self.restart_count += 1
            self.start()

def main():
    logger.info("="*50)
    logger.info("   MetaPassiveIncome Autonomous System Launcher")
    logger.info("   - Dashboard")
    logger.info("   - Payment Server")
    logger.info("   - Auto Mode Daemon")
    logger.info("="*50)

    python_exe = sys.executable

    services = [
        ServiceManager("Dashboard", [python_exe, "dashboard_server.py"], port=8099),
        ServiceManager("PaymentServer", [python_exe, "backend/payment_server.py"], port=5000),
        # Daemon은 포트가 없으므로 프로세스 상태로만 체크
        ServiceManager("AutoDaemon", [python_exe, "auto_mode_daemon.py", "--interval", "300", "--batch", "1"]) 
    ]

    # 초기 실행
    for service in services:
        service.start()
        time.sleep(2) # 순차 실행 대기

    logger.info("✨ All systems initialized. Monitoring loop started.")
    
    try:
        while True:
            for service in services:
                service.monitor()
            time.sleep(10) # 10초마다 상태 확인
    except KeyboardInterrupt:
        logger.info("🛑 Stopping launcher...")
        # 자식 프로세스 정리
        for s in services:
             if s.process:
                 s.process.terminate()
        sys.exit(0)

if __name__ == "__main__":
    main()
