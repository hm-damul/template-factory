
import sys
import os
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

from src.publisher import Publisher
from src.ledger_manager import LedgerManager
from src.config import Config

def main():
    print("Starting cleanup...")
    
    # Initialize LedgerManager
    # db_path logic in main code uses sqlite:///... format for database_url usually
    db_path = project_root / "data" / "ledger.db"
    database_url = f"sqlite:///{db_path}"
    ledger_manager = LedgerManager(database_url=database_url)
    
    # Initialize Publisher
    publisher = Publisher(ledger_manager)
    
    # Run cleanup
    # We want to ensure we have room for 117 products. 
    # Vercel limit is 200. Let's aim for 150 to be safe.
    # If we have 200 projects, we need to delete at least 50.
    publisher.cleanup_old_projects(max_projects=150)
    
    print("Cleanup finished.")

if __name__ == "__main__":
    main()
