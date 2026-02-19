import os
import sys
import winreg
import logging
from pathlib import Path

# 설정
PROJECT_ROOT = Path(__file__).parent.absolute()
BAT_FILE = PROJECT_ROOT / "start_autonomous_system.bat"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AutoRunSetup")

def add_to_startup():
    """
    현재 사용자의 시작프로그램 폴더에 바로가기를 생성합니다.
    """
    try:
        # 시작프로그램 폴더 경로 찾기
        startup_folder = os.path.join(os.getenv('APPDATA'), r'Microsoft\Windows\Start Menu\Programs\Startup')
        shortcut_path = os.path.join(startup_folder, "MetaPassiveIncome_Auto.lnk")
        
        logger.info(f"Adding to startup folder: {startup_folder}")
        
        # 기존 바로가기가 있다면 삭제 시도 (잠금 해제 목적)
        if os.path.exists(shortcut_path):
            try:
                os.remove(shortcut_path)
                logger.info(f"Deleted existing shortcut: {shortcut_path}")
            except Exception as e:
                logger.warning(f"Could not delete existing shortcut: {e}")

        # PowerShell을 사용하여 바로가기 생성 (.lnk)
        # Python만으로는 .lnk 파일 생성이 복잡하므로 PowerShell COM 객체 활용
        ps_script = f"""
        $WshShell = New-Object -comObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
        $Shortcut.TargetPath = "{BAT_FILE}"
        $Shortcut.WorkingDirectory = "{PROJECT_ROOT}"
        $Shortcut.Description = "Auto Start MetaPassiveIncome System"
        $Shortcut.Save()
        """
        
        # PowerShell 실행
        import subprocess
        subprocess.run(["powershell", "-Command", ps_script], check=True)
        
        logger.info(f"✅ Successfully created shortcut at: {shortcut_path}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to add to startup: {e}")
        return False

if __name__ == "__main__":
    if add_to_startup():
        print("\n✨ 시스템이 시작프로그램에 성공적으로 등록되었습니다.")
        print("이제 컴퓨터를 켜면 자동으로 판매 시스템이 시작됩니다.")
    else:
        print("\n⚠️ 자동 실행 등록에 실패했습니다.")
