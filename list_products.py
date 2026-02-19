from src.ledger_manager import LedgerManager
from src.config import Config
import json

def list_products():
    lm = LedgerManager(Config.DATABASE_URL)
    products = lm.list_products()
    print(json.dumps(products, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    list_products()
