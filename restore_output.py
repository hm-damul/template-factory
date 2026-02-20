
import os
import shutil
import sys

def main():
    if len(sys.argv) < 2:
        print("Usage: python restore_output.py <product_id>")
        sys.exit(1)
        
    product_id = sys.argv[1]
    public_path = os.path.join("public", "outputs", product_id)
    output_path = os.path.join("outputs", product_id)
    
    if not os.path.exists(public_path):
        print(f"Public path not found: {public_path}")
        sys.exit(1)
        
    if os.path.exists(output_path):
        print(f"Output path already exists: {output_path}")
        # If it exists, maybe it's empty? check content
        if not os.listdir(output_path):
            print("But it is empty. Removing and copying...")
            os.rmdir(output_path)
        else:
            print("Skipping restore.")
            sys.exit(0)
            
    print(f"Restoring {output_path} from {public_path}...")
    shutil.copytree(public_path, output_path)
    print("Done.")

if __name__ == "__main__":
    main()
