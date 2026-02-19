
import sys
import os
from pathlib import Path
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 현재 디렉토리를 경로에 추가
sys.path.append(str(Path.cwd()))

try:
    from src.publisher import Publisher
    from src.ledger_manager import LedgerManager
    from src.utils import ProductionError

    lm = LedgerManager()
    p = Publisher(lm)

    product_id = '20260215-185109-token-gated-content-revenue-au'
    product_dir = str(Path('outputs') / product_id)

    if not os.path.exists(product_dir):
        print(f"ERROR: 디렉토리가 없습니다: {product_dir}")
        sys.exit(1)

    print(f"Publishing product: {product_id} from {product_dir}")
    result = p.publish_product(product_id, product_dir)
    print(f"SUCCESS: {result}")

except Exception as e:
    print(f"FAILURE: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
