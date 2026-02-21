import os
import shutil
import subprocess
from pathlib import Path

def run_cmd(cmd):
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def fix_deployment():
    root = Path(".")
    outputs_dir = root / "outputs"
    public_outputs_dir = root / "public" / "outputs"
    
    print("Copying outputs to public/outputs...")
    if outputs_dir.exists():
        if public_outputs_dir.exists():
            # shutil.rmtree(public_outputs_dir) # Don't delete, merge/overwrite
            pass
        os.makedirs(public_outputs_dir, exist_ok=True)
        
        # Copy recursively
        # shutil.copytree(outputs_dir, public_outputs_dir, dirs_exist_ok=True)
        # copytree might be slow for huge dirs, let's just copy what we need or everything
        # For now, copy everything to be safe
        shutil.copytree(outputs_dir, public_outputs_dir, dirs_exist_ok=True)
        
    print("Adding files to git...")
    run_cmd(["git", "add", "public/"])
    run_cmd(["git", "add", ".vercelignore"])
    
    print("Committing...")
    try:
        run_cmd(["git", "commit", "-m", "fix-deployment-size-limit"])
    except subprocess.CalledProcessError:
        print("Nothing to commit?")
        
    print("Pushing...")
    run_cmd(["git", "push", "origin", "main"])
    
    print("Done!")

if __name__ == "__main__":
    fix_deployment()
