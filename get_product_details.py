from src.ledger_manager import LedgerManager
import json

def get_product_details(pid):
    lm = LedgerManager()
    prod = lm.get_product(pid)
    print(json.dumps(prod, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    get_product_details('20260213-154551-프리랜서-컨설턴트-서비스-소개-랜딩-페이지')
