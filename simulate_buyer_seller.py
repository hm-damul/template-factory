import os
import sys
import glob
from concurrent.futures import ThreadPoolExecutor

# Add src to path
sys.path.append(os.getcwd())
from src.local_verifier import LocalVerifier

OUTPUTS_DIR = os.path.join(os.getcwd(), 'outputs')

def run_simulation():
    print("Starting Buyer/Seller Simulation & Repair Bot (using LocalVerifier)...")
    dirs = [d for d in glob.glob(os.path.join(OUTPUTS_DIR, '*')) if os.path.isdir(d)]
    print(f"Found {len(dirs)} products. Processing...")
    
    verifier = LocalVerifier()
    
    # Use threading to speed up file I/O and processing
    with ThreadPoolExecutor(max_workers=20) as executor:
        executor.map(verifier.verify_and_repair_product, dirs)
        
    print("Simulation and Repair Complete.")
    print("All products have been updated with the latest checkout flow.")

if __name__ == "__main__":
    run_simulation()
