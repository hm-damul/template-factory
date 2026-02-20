# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import argparse
import subprocess
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

# Root Path
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.append(str(PROJECT_ROOT))

# Import core modules
from src.ledger_manager import LedgerManager
from src.config import Config
from src.publisher import Publisher
from promotion_dispatcher import dispatch_publish, load_channel_config, repromote_best_sellers
from src.key_manager import KeyManager
from src.comment_bot import CommentBot
from src.error_learning_system import get_error_system
import requests
import re

# Logging configuration
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "auto_mode_daemon.log"

# Clear existing log file if it's very old or just for fresh start
if LOG_FILE.exists() and LOG_FILE.stat().st_size == 0:
    pass # Keep it

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8", delay=False),
        logging.StreamHandler(sys.stdout)
    ],
    force=True
)
logger = logging.getLogger("AutoModeDaemon")

STATUS_FILE = PROJECT_ROOT / "data" / "daemon_status.json"

def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _update_status(update: Dict[str, Any]):
    status = {}
    if STATUS_FILE.exists():
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                status = json.load(f)
        except Exception:
            pass
    status.update(update)
    status["last_updated"] = _utc_iso()
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(status, f, indent=2, ensure_ascii=False)
    except Exception as e:
        # 파일 쓰기 실패는 로깅하되 크래시되지 않도록 함
        print(f"Status file write failed: {e}")
        pass 

def logger_info(msg: str):
    logger.info(msg)
    _update_status({"last_log": msg})

def _retry_pending_deployments():
    """배포 대기 중인 제품들(WAITING_FOR_DEPLOYMENT) 재시도"""
    try:
        lm = LedgerManager(Config.DATABASE_URL)
        pub = Publisher(lm)
        waiting = lm.get_products_by_status("WAITING_FOR_DEPLOYMENT")
        
        if not waiting:
            return
            
        logger_info(f"대기 중인 제품 {len(waiting)}개 재배포 시도 중...")
        
        # 프로젝트 한도 도달 가능성이 있으므로 미리 정리 시도
        try:
            pub.cleanup_old_projects(max_projects=150)
        except Exception as e:
            logger_info(f"Vercel 프로젝트 정리 중 오류 (무시하고 진행): {e}")

        product_ids = []
        for p in waiting:
            pid = p["id"]
            output_dir = PROJECT_ROOT / "outputs" / pid
            if output_dir.exists():
                # 배포 전 결제 위젯 확인 및 주입 (기존 누락분 대응)
                index_html = output_dir / "index.html"
                if index_html.exists():
                    content = index_html.read_text(encoding="utf-8", errors="ignore")
                    if "startPay" not in content and "choose-plan" not in content and "crypto-payment-widget" not in content:
                        logger_info(f"[{pid}] 결제 위젯 누락 감지. 주입 시도...")
                        try:
                            from monetize_module import MonetizeModule, PaymentInjectConfig
                            mm = MonetizeModule()
                            mm.inject_payment_logic(str(index_html), PaymentInjectConfig(product_id=pid))
                            logger_info(f"[{pid}] 결제 위젯 주입 완료.")
                        except Exception as e:
                            logger_info(f"[{pid}] 결제 위젯 주입 실패: {e}")
                
                product_ids.append(pid)
        
        if product_ids:
            logger_info(f"배치 배포 시작: {len(product_ids)}개 제품")
            # Batch publish call
            try:
                results = pub.publish_products_batch(product_ids)
                
                for pid, res in results.items():
                    if res.get("status") == "PUBLISHED":
                        logger_info(f"재배포 성공: {pid}")
                    elif res.get("status") == "WAITING_VERIFICATION":
                        logger_info(f"재배포 검증 대기: {pid} (URL: {res.get('url')})")
                    else:
                        err_msg = str(res.get("error", ""))
                        logger_info(f"재배포 실패: {pid} ({err_msg})")
            except Exception as e:
                logger_info(f"배치 배포 중 치명적 오류: {e}")
    except Exception as e:
        logger_info(f"재배포 프로세스 전체 오류: {e}")

def _run_auto_heal():
    """실패한 제품들을 자동으로 복구"""
    cmd = [sys.executable, "auto_heal_products.py"]
    logger_info("자동 복구(Auto-heal) 프로세스 시작...")
    try:
        # 쉘 실행 시 인코딩 문제 방지를 위해 env 설정
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        subprocess.run(cmd, cwd=str(PROJECT_ROOT), shell=False, env=env)
        logger_info("자동 복구 프로세스 완료.")
    except Exception as e:
        logger_info(f"자동 복구 프로세스 오류: {e}")

def _promote_published_backlog():
    """PUBLISHED 상태로 남아있는 제품들 프로모션 실행"""
    try:
        from promotion_dispatcher import dispatch_publish
        lm = LedgerManager(Config.DATABASE_URL)
        products = lm.list_products()
        published = [p for p in products if p['status'] == 'PUBLISHED']
        
        if not published:
            return
            
        logger_info(f"프로모션 대기 중인 제품 {len(published)}개 처리 시작...")
        _update_status({"phase": "promoting_backlog", "count": len(published)})
        for p in published:
            pid = p['id']
            _update_status({"phase": "promoting", "product_id": pid, "action": "Posting to channels"})
            try:
                res = dispatch_publish(pid)
                if res.get("dispatch_results", {}).get("wordpress", {}).get("ok"):
                    logger_info(f"프로모션 성공: {pid}")
                else:
                    logger_info(f"프로모션 실패: {pid}")
                time.sleep(2)
            except Exception as e:
                logger_info(f"프로모션 중 예외 ({pid}): {e}")
    except Exception as e:
        logger_info(f"프로모션 백로그 처리 중 오류: {e}")
    finally:
        _update_status({"phase": "idle", "product_id": None})

# -----------------------------
# Service Monitor
# -----------------------------
def _kill_port(port: int):
    """특정 포트를 사용하는 프로세스 강제 종료 (Windows)"""
    if os.name != 'nt':
        return
    try:
        cmd = f"netstat -ano"
        output = subprocess.check_output(cmd, shell=True).decode('cp949', errors='ignore')
        for line in output.splitlines():
            if "LISTENING" in line and f":{port}" in line:
                parts = line.strip().split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    if pid and pid != "0":
                        if int(pid) == os.getpid():
                            continue
                        subprocess.run(["taskkill", "/PID", pid, "/F", "/T"], capture_output=True)
    except Exception:
        pass

def _start_background_process(name: str, cmd: List[str]):
    """백그라운드로 프로세스 실행 (로그 파일로 리다이렉션)"""
    log_path = LOGS_DIR / f"{name}.log"
    f = log_path.open("w", encoding="utf-8")
    try:
        env = os.environ.copy()
        env.pop("WERKZEUG_RUN_MAIN", None)
        env.pop("WERKZEUG_SERVER_FD", None)
        
        if os.name == 'nt':
            # Windows: CREATE_NO_WINDOW or similar if possible, but Popen defaults to hidden if shell=False and not GUI
            # actually standard Popen with stdout redirection is usually enough to not pop up if not using shell=True
            subprocess.Popen(
                cmd,
                cwd=str(PROJECT_ROOT),
                stdout=f,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                shell=False,
                env=env,
                close_fds=True
            )
        else:
            subprocess.Popen(
                cmd,
                cwd=str(PROJECT_ROOT),
                stdout=f,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                shell=False,
                env=env,
                start_new_session=True
            )
        logger_info(f"🟢 {name} started in background. Logs: {log_path}")
    except Exception as e:
        logger_info(f"Failed to start {name}: {e}")
        f.close()

def _check_and_start_services():
    """결제 서버(5000)와 프리뷰 서버(8090)가 죽어있으면 살립니다."""
    services = [
            {"name": "Payment Server", "port": 5000, "script": "api/main.py", "url": "http://127.0.0.1:5000/health"},
            {"name": "Preview Server", "port": 8088, "script": "preview_server.py", "url": "http://127.0.0.1:8088/health"},
            {"name": "Dashboard", "port": 8099, "script": "dashboard_server.py", "url": "http://127.0.0.1:8099/health"},
        ]
    
    for svc in services:
        is_running = False
        try:
            r = requests.get(svc["url"], timeout=2)
            if r.status_code == 200:
                is_running = True
        except:
            pass
        
        if not is_running:
            logger_info(f"🔴 {svc['name']} is DOWN. Cleaning port {svc['port']} and restarting...")
            
            # 1. Kill zombie processes on the port
            _kill_port(svc['port'])
            time.sleep(1)
            
            # 2. Start process
            cmd = [sys.executable, svc["script"]]
            _start_background_process(svc["name"], cmd)
            
            time.sleep(5) # Wait for startup

    # Check Dashboard (Self-check not needed as we are daemon, but maybe check 8099?)
    try:
        r = requests.get("http://127.0.0.1:8099/health", timeout=2)
        if r.status_code == 200:
            # Trigger sync if dashboard is up
            try:
                requests.post("http://127.0.0.1:8099/api/system/sync_products", timeout=5)
            except:
                pass
    except:
        logger_info("🟠 Dashboard (8099) seems down. Attempting to restart...")
        _kill_port(8099)
        cmd = [sys.executable, "dashboard_server.py"]
        _start_background_process("dashboard", cmd)

def _run_autopilot(batch: int, topic: str, deploy: bool) -> Dict[str, Any]:
    cmd: List[str] = [sys.executable, "auto_pilot.py", "--batch", str(int(batch))]
    if topic:
        cmd += ["--topic", topic]
    
    _update_status({"phase": "running_autopilot", "last_cmd": cmd, "action": "Creating/Updating Product"})
    
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    
    output_lines = []
    rc = 0
    
    try:
        # Run with Popen to capture and print output in real-time
        process = subprocess.Popen(
            cmd, cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, bufsize=1, encoding='utf-8', errors='replace'
        )
        
        for line in process.stdout:
            print(line, end='')
            output_lines.append(line)
            
        process.wait()
        rc = process.returncode
        
        if rc != 0:
            logger_info(f"Auto-pilot failed with return code {rc}")
            try:
                error_system = get_error_system()
                context = f"Running auto_pilot.py with args: {cmd}"
                error_log = "".join(output_lines[-100:]) # Analyze last 100 lines
                analysis = error_system.analyze_and_fix(Exception(f"Process failed with RC {rc}. Log tail:\n{error_log}"), context=context)
                
                if analysis.get("confidence", 0) > 0.8:
                     logger_info(f"AI Suggested Fix for Auto-pilot: {analysis.get('details')}")
                     if error_system.apply_fix(analysis):
                         logger_info("Auto-fix applied. Retrying auto-pilot...")
                         # Retry once
                         process = subprocess.Popen(
                            cmd, cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, bufsize=1, encoding='utf-8', errors='replace'
                         )
                         for line in process.stdout:
                             print(line, end='')
                         process.wait()
                         rc = process.returncode
            except Exception as e:
                logger_info(f"Error analysis failed: {e}")
                
    except Exception as e:
        logger_info(f"Subprocess execution failed: {e}")
        rc = -1
        
    _update_status({"phase": "autopilot_finished", "rc": rc})
    return {"rc": rc, "out": "Output logged"}

def _discover_new_products(since_ts: float) -> List[str]:
    outputs = PROJECT_ROOT / "outputs"
    if not outputs.exists():
        return []
    new_ids: List[str] = []
    for d in outputs.iterdir():
        if not d.is_dir():
            continue
        try:
            if d.stat().st_mtime >= since_ts:
                new_ids.append(d.name)
        except Exception:
            continue
    new_ids.sort()
    return new_ids

def _check_wordpress_comments():
    """워드프레스 댓글을 통한 상품 재생성 요청 확인"""
    try:
        cfg = load_channel_config()
        blog_cfg = cfg.get("blog", {})
        wp_api_url = blog_cfg.get("wp_api_url")
        wp_token = blog_cfg.get("wp_token")
        
        if not wp_api_url or not wp_token:
            return

        # 댓글 엔드포인트
        base_url = wp_api_url.split('/wp/v2/')[0] + '/wp/v2/comments'
        headers = {}
        if ":" in wp_token:
            import base64
            encoded_auth = base64.b64encode(wp_token.encode("utf-8")).decode("utf-8")
            headers["Authorization"] = f"Basic {encoded_auth}"
        else:
            headers["Authorization"] = f"Bearer {wp_token}"
            
        r = requests.get(base_url, headers=headers, params={"per_page": 10, "status": "approve"}, timeout=10)
        if r.status_code != 200:
            return
            
        comments = r.json()
        processed_file = PROJECT_ROOT / "data" / "processed_comments.json"
        processed_ids = []
        if processed_file.exists():
            try:
                processed_ids = json.loads(processed_file.read_text())
            except: pass

        lm = LedgerManager(Config.DATABASE_URL)
        new_processed = False
        
        for c in comments:
            c_id = c.get("id")
            if c_id in processed_ids:
                continue
            
            content = c.get("content", {}).get("rendered", "").lower()
            keywords = ["request", "recreate", "buy", "purchase", "결제", "구매", "요청", "살게요", "재생성"]
            
            if any(k in content for k in keywords):
                post_id = c.get("post")
                # 포스트 본문에서 product_id 추출 시도
                post_url = wp_api_url.split('/wp/v2/')[0] + f'/wp/v2/posts/{post_id}'
                pr = requests.get(post_url, headers=headers, timeout=10)
                if pr.status_code == 200:
                    p_data = pr.json()
                    p_content = p_data.get("content", {}).get("rendered", "")
                    p_slug = p_data.get("slug", "")
                    
                    product_id = None
                    # 1. data-product-id 속성
                    m = re.search(r'data-product-id=["\']([^"\']+)["\']', p_content)
                    if m: product_id = m.group(1)
                    # 2. 슬러그에서 ID 패턴 추출
                    if not product_id:
                        m = re.search(r'(\d{8}-\d{6}-[a-zA-Z0-9\-]+)', p_slug)
                        if m: product_id = m.group(1)
                        
                        if product_id:
                            prod = lm.get_product(product_id)
                            # 상품이 없거나, 실패 상태거나, 명시적으로 재생성 요청이 있는 경우 진행
                            should_recreate = False
                            if not prod:
                                should_recreate = True
                            elif prod.get("status") in ["PIPELINE_FAILED", "CRITICAL_FAILED", "QA_FAILED", "DELETED"]:
                                should_recreate = True
                            
                            if should_recreate:
                                logger_info(f"댓글 요청으로 인한 상품 재생성 시작: {product_id}")
                                # 중복 실행 방지를 위해 즉시 처리된 것으로 간주 (또는 별도 락 파일 사용 가능)
                                # 재생성 트리거 (auto_pilot 호출, product_id 전달)
                                parts = product_id.split('-', 2)
                                topic = parts[2] if len(parts) > 2 else "requested"
                                subprocess.Popen([sys.executable, "auto_pilot.py", "--batch", "1", "--topic", topic, "--product_id", product_id, "--deploy", "1"])
                            else:
                                logger_info(f"댓글 요청이 있으나 상품이 이미 양호한 상태입니다: {product_id} ({prod.get('status')})")
            
            processed_ids.append(c_id)
            new_processed = True
            
        if new_processed:
            processed_file.write_text(json.dumps(processed_ids))
            
    except Exception as e:
        logger_info(f"WordPress 댓글 확인 중 오류: {e}")
        try:
            error_system = get_error_system()
            analysis = error_system.analyze_and_fix(e, context="Checking WordPress comments")
            if analysis.get("confidence", 0) > 0.8 and error_system.apply_fix(analysis):
                logger_info("Auto-fix applied. Retrying comment check...")
                _check_wordpress_comments()
        except Exception as ai_e:
            logger_info(f"AI error analysis failed: {ai_e}")

def _run_system_audit():
    """시스템 상시 검수 실행"""
    logger_info("시스템 상시 검수 봇 가동...")
    try:
        from src.audit_bot import SystemAuditBot
        bot = SystemAuditBot()
        report = bot.run_full_audit()
        healthy = report["summary"]["healthy_products"]
        total = report["summary"]["total_products"]
        logger_info(f"검수 완료: 정상 상품 {healthy}/{total}")
    except Exception as e:
        logger_info(f"시스템 검수 중 오류 발생: {e}")
        try:
            error_system = get_error_system()
            analysis = error_system.analyze_and_fix(e, context="Running system audit")
            if analysis.get("confidence", 0) > 0.8 and error_system.apply_fix(analysis):
                logger_info("Auto-fix applied. Retrying system audit...")
                _run_system_audit()
        except Exception as ai_e:
            logger_info(f"AI error analysis failed: {ai_e}")

def _run_market_analysis():
    """시장 분석 및 가격 최적화 실행"""
    logger_info("시장 분석 및 가격 최적화 봇 가동...")
    try:
        from src.market_analyzer import MarketAnalyzer
        from src.ledger_manager import LedgerManager
        from src.config import Config
        
        analyzer = MarketAnalyzer(PROJECT_ROOT)
        stats, updated_ids = analyzer.analyze_and_optimize()
        
        if stats:
            logger_info(f"가격 최적화 완료: {json.dumps(stats, ensure_ascii=False)}")
            
        # 업데이트된 제품이 있으면 상태를 WAITING_FOR_DEPLOYMENT로 변경하여 재배포 유도
        if updated_ids:
            logger_info(f"업데이트된 제품 {len(updated_ids)}개를 재배포 대기열에 추가합니다.")
            try:
                lm = LedgerManager(Config.DATABASE_URL)
                for pid in updated_ids:
                    # 현재 상태가 PUBLISHED인 경우에만 재배포 대기로 변경 (실패한 것은 놔둠)
                    prod = lm.get_product(pid)
                    if prod and prod.get("status") == "PUBLISHED":
                        lm.update_product(pid, status="WAITING_FOR_DEPLOYMENT")
                        logger_info(f"[{pid}] 가격 변동으로 인한 재배포 요청됨.")
            except Exception as e:
                logger_info(f"재배포 상태 업데이트 중 오류: {e}")
                
    except Exception as e:
        logger_info(f"시장 분석 중 오류 발생: {e}")
        try:
            error_system = get_error_system()
            analysis = error_system.analyze_and_fix(e, context="Running market analysis")
            if analysis.get("confidence", 0) > 0.8 and error_system.apply_fix(analysis):
                logger_info("Auto-fix applied. Retrying market analysis...")
                _run_market_analysis()
        except Exception as ai_e:
            logger_info(f"AI error analysis failed: {ai_e}")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=3600, help="seconds between runs")
    ap.add_argument("--batch", type=int, default=1, help="products per run")
    ap.add_argument("--topic", type=str, default="", help="optional topic, blank=auto")
    ap.add_argument("--deploy", type=int, default=0, help="1 to deploy to vercel")
    ap.add_argument(
        "--publish",
        type=int,
        default=1,
        help="1 to create ready_to_publish and optionally webhook post",
    )
    ap.add_argument("--max_runs", type=int, default=0, help="0=forever")
    args = ap.parse_args()

    interval = max(60, int(args.interval))
    batch = max(1, int(args.batch))
    topic = str(args.topic or "").strip()
    deploy = bool(int(args.deploy))
    publish = bool(int(args.publish))
    max_runs = int(args.max_runs)

    # 0. 초기 키 스캔 (Auto Key Extraction)
    try:
        km = KeyManager(PROJECT_ROOT)
        km.scan_and_extract()
    except Exception as e:
        logger_info(f"키 매니저 초기화 오류: {e}")

    # 0.5 댓글 봇 초기화
    comment_bot = None
    try:
        # Load secrets fresh
        with open(PROJECT_ROOT / "data" / "secrets.json", "r", encoding="utf-8") as f:
            secrets = json.load(f)
        if secrets.get("WP_API_URL") and secrets.get("WP_TOKEN"):
            comment_bot = CommentBot(secrets["WP_API_URL"], secrets["WP_TOKEN"])
            logger_info("🤖 댓글 관리 봇(CommentBot) 활성화됨")
    except Exception as e:
        logger_info(f"댓글 봇 초기화 실패 (스킵): {e}")

    run_count = 0
    consecutive_failures = 0
    MAX_CONSECUTIVE_FAILURES = 5

    logger_info(f"DAEMON STARTED: interval={interval}s, batch={batch}, topic='{topic}'")
    _update_status({"status": "running", "pid": os.getpid(), "start_time": _utc_iso()})

    try:
        while True:
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                logger_info(f"연속 {consecutive_failures}회 실패 발생. 안전을 위해 데몬을 1시간 동안 중단합니다.")
                _update_status({"status": "paused", "reason": "too_many_failures"})
                time.sleep(3600)
                consecutive_failures = 0
                continue

            run_count += 1
            if max_runs > 0 and run_count > max_runs:
                logger_info(f"Max runs ({max_runs}) reached. Exiting.")
                break

            start_time = time.time()
            logger_info(f"--- RUN #{run_count} START ---")
            
            try:
                # -1. 서비스 헬스 체크 및 자동 시작
                _check_and_start_services()

                # 0. 워드프레스 댓글 확인 (재생성 요청)
                _check_wordpress_comments()

                # 1. 재배포 시도 (Vercel 한도 등으로 밀린 것들)
                _retry_pending_deployments()

                # 2. 시스템 상태 검수 (배포 후 상태 확인 및 자동 복구 트리거)
                # _run_system_audit() 은 run_count가 5의 배수일 때만 실행 (매 시간 1회 정도)
                if run_count % 5 == 1:
                    _run_system_audit()
                
                # 2.5 시장 분석 및 가격 최적화 (매 회 실행하여 가격 동기화 유지)
                _run_market_analysis()

                # 3. 헬스 리포트 생성
                try:
                    subprocess.run([sys.executable, "generate_health_report.py"], check=False)
                except:
                    pass
                
                # 3.5 프로모션 백로그 처리 (누락된 홍보 자동 수행)
                _promote_published_backlog()

                # 4. 오토파일럿 실행 (생성 -> 배포)
                res = _run_autopilot(batch, topic, deploy)
                logger_info(f"Autopilot finished (rc={res['rc']})")
                
                if res['rc'] == 0:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    logger_info(f"Autopilot failed. 연속 실패 횟수: {consecutive_failures}")

                # 5. 새로운 제품들 홍보 채널로 발행 (WordPress, X 등)
                _promote_published_backlog()

                # 5.5 성과 기반 재홍보 (3회 실행마다 1번)
                if run_count % 3 == 0:
                    logger_info("성과 기반 재홍보(Analytics Loop) 실행...")
                    try:
                        repromote_best_sellers()
                    except Exception as e:
                        logger_info(f"재홍보 실행 중 오류: {e}")

                # 5.6 댓글 자동 응답 (매 실행마다)
                if comment_bot:
                    logger_info("댓글 봇 실행 중...")
                    try:
                        comment_bot.run_cycle()
                    except Exception as e:
                        logger_info(f"댓글 봇 실행 오류: {e}")

                if publish:
                    new_pids = _discover_new_products(start_time)
                    if new_pids:
                        logger_info(f"발견된 새 제품 {len(new_pids)}개 홍보 발행 상태 확인/업데이트...")
                        for pid in new_pids:
                            try:
                                # promotion_dispatcher를 통해 WordPress, X 등으로 전송 (이미 되어있으면 업데이트)
                                dispatch_publish(pid)
                                logger_info(f"홍보 발행 완료: {pid}")
                            except Exception as e:
                                logger_info(f"홍보 발행 중 오류 ({pid}): {e}")

                # 6. 자동 복구 시도
                _run_auto_heal()

                # 7. 주기적인 배포 프로젝트 정리 (Git Push 모드에서는 불필요하므로 비활성화)
                # try:
                #     from src.publisher import Publisher
                #     from src.ledger_manager import LedgerManager
                #     from src.config import Config
                #     pub = Publisher(LedgerManager(Config.DATABASE_URL))
                #     pub.cleanup_old_projects(max_projects=190) # 한도를 190으로 완화 (실제 한도 200)
                # except Exception as e:
                #     logger_info(f"Vercel 정기 정리 중 오류: {e}")

            except Exception as run_err:
                consecutive_failures += 1
                logger_info(f"루틴 실행 중 예외 발생: {run_err}. 연속 실패 횟수: {consecutive_failures}")

            elapsed = time.time() - start_time
            wait_sec = max(10, interval - elapsed)
            logger_info(f"--- RUN #{run_count} END (took {elapsed:.1f}s). Next run in {wait_sec:.1f}s ---")
            
            _update_status({
                "phase": "sleeping",
                "last_run_end": _utc_iso(),
                "next_run_approx": datetime.fromtimestamp(time.time() + wait_sec, timezone.utc).isoformat()
            })
            
            # Smart sleep with service monitoring
            next_run_time = time.time() + wait_sec
            while time.time() < next_run_time:
                remaining = next_run_time - time.time()
                # Check services every 60 seconds or remaining time
                sleep_chunk = min(remaining, 60)
                if sleep_chunk <= 0:
                    break
                time.sleep(sleep_chunk)
                
                # Periodic service check
                try:
                    _check_and_start_services()
                except Exception:
                    pass

    except KeyboardInterrupt:
        logger_info("Daemon stopped by user.")
    except Exception as e:
        logger_info(f"Daemon crashed: {e}")
        import traceback
        logger_info(traceback.format_exc())
        return 1
    finally:
        _update_status({"status": "stopped", "stop_time": _utc_iso()})

    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"FATAL ERROR in Auto Mode Daemon: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")
        sys.exit(1)
