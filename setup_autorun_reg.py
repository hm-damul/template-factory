import winreg
import os
import sys

def add_to_registry():
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    app_name = "MetaPassiveIncome_Auto"
    bat_path = os.path.join(os.getcwd(), "start_autonomous_system.bat")
    
    try:
        # Open the key for writing
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{bat_path}"')
        winreg.CloseKey(key)
        print(f"✅ Successfully added to Registry: {key_path} -> {app_name}")
        return True
    except Exception as e:
        print(f"❌ Failed to add to Registry: {e}")
        return False

if __name__ == "__main__":
    add_to_registry()
