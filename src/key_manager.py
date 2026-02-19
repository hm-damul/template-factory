import os
import re
import json
from pathlib import Path
from typing import Dict, Optional

class KeyManager:
    """
    Helper to extract API keys and secrets from environment files or config.
    Centralizes credentials into secrets.json.
    """
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.secrets_file = project_root / "data" / "secrets.json"
        self.env_file = project_root / ".env"
        
        self.known_keys = [
            "OPENAI_API_KEY", "GEMINI_API_KEY", "VERCEL_API_TOKEN", 
            "WP_API_URL", "WP_TOKEN", "MEDIUM_TOKEN", 
            "PINTEREST_ACCESS_TOKEN", "X_CONSUMER_KEY", "X_ACCESS_TOKEN"
        ]

    def load_secrets(self) -> Dict[str, str]:
        if self.secrets_file.exists():
            with open(self.secrets_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_secrets(self, secrets: Dict[str, str]):
        self.secrets_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.secrets_file, "w", encoding="utf-8") as f:
            json.dump(secrets, f, indent=4)
        print(f"[KeyManager] Secrets updated in {self.secrets_file}")

    def scan_and_extract(self):
        """
        Scans .env file and extracts keys to secrets.json.
        """
        secrets = self.load_secrets()
        updated = False
        
        # 1. Scan .env
        if self.env_file.exists():
            print(f"[KeyManager] Scanning .env file...")
            with open(self.env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        key, value = parts[0].strip(), parts[1].strip().strip('"').strip("'")
                        
                        if key in self.known_keys and not secrets.get(key):
                            secrets[key] = value
                            print(f"   -> Extracted {key}")
                            updated = True
        
        # 2. Scan system env vars
        for key in self.known_keys:
            val = os.getenv(key)
            if val and not secrets.get(key):
                secrets[key] = val
                print(f"   -> Extracted {key} from System Env")
                updated = True
                
        if updated:
            self.save_secrets(secrets)
        else:
            print("[KeyManager] No new keys found to extract.")

def apply_keys(project_root=None, write=False, inject=True):
    """
    Loads secrets from secrets.json and injects them into os.environ.
    Useful for scripts that need API keys.
    """
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent
        
    manager = KeyManager(project_root)
    secrets = manager.load_secrets()
    
    if inject:
        for k, v in secrets.items():
            # Don't overwrite existing env vars to allow manual overrides
            if k not in os.environ:
                os.environ[k] = str(v)
                # print(f"Loaded {k} from secrets")

if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    manager = KeyManager(root)
    manager.scan_and_extract()
