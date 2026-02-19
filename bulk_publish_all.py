# -*- coding: utf-8 -*-
import subprocess
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_publish_batches(batch_size=100, total_limit=1000):
    published_so_far = 0
    while published_so_far < total_limit:
        logger.info(f"Starting batch: {published_so_far} to {published_so_far + batch_size}")
        
        # bulk_publish_promos.py는 항상 최근 수정된 순서로 가져오므로, 
        # 이미 발행된 것은 publish_results.json이 최신화되어 뒤로 밀리거나 할 수 있음.
        # 하지만 현재 로직상 최근 수정된 순서대로 limit만큼 가져오므로 
        # 재생성된 것들을 순차적으로 처리하게 됨.
        
        try:
            # subprocess를 사용하여 실행
            res = subprocess.run(["python", "bulk_publish_promos.py", str(batch_size)], capture_output=True, text=True)
            logger.info(res.stdout)
            if res.stderr:
                logger.error(res.stderr)
            
            published_so_far += batch_size
            logger.info(f"Finished batch. Total attempted: {published_so_far}")
            
            # WP 서버 부하 방지를 위해 30초 대기
            if published_so_far < total_limit:
                logger.info("Waiting 30 seconds before next batch...")
                time.sleep(30)
                
        except Exception as e:
            logger.error(f"Error in batch: {e}")
            break

if __name__ == "__main__":
    run_publish_batches(batch_size=50, total_limit=950)
