from src.auto_heal_system import VercelAPIDeployerWrapper
import logging
import sys

def test_deploy():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    deployer = VercelAPIDeployerWrapper()
    
    # Create a dummy file
    files = [("index.html", b"<html><body><h1>Hello World</h1></body></html>")]
    
    # Bypass the auto-heal file collection logic by calling deploy_static_files directly if possible,
    # but VercelAPIDeployerWrapper.deploy() adds vercel.json etc.
    # Let's import deploy_static_files directly.
    try:
        from deploy_module_vercel_api import deploy_static_files
        
        project_name = "test-deploy-simple-public"
        print(f"Deploying {project_name}...")
        
        url = deploy_static_files(project_name, files, production=True)
        print(f"URL: {url}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_deploy()
