# -*- coding: utf-8 -*-
"""
dashboard_server.py

목적:
- 로컬 관리 대시보드(포트 8099)
- 서버 제어: Payment/Preview 시작/중지 + 상태/PID
- 파이프라인: auto_pilot 실행(batch N), product 재생성, 삭제
- 제품 관리: outputs 목록, 링크(미리보기/결제테스트/다운로드)
- 주문 뷰어: data/orders.json 조회 + 테스트용 paid 마킹
- 홍보: Publish 버튼(ready_to_publish.json 생성)

실행:
  python dashboard_server.py
접속:
  http://127.0.0.1:8099/
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List

import requests
from flask import (
    Flask,
    flash,
    abort,
    jsonify,
    redirect,
    render_template_string,
    request,
    Response,
    send_file,
    send_from_directory,
    url_for,
)

from order_store import FileOrderStore
from src.ledger_manager import LedgerManager, Order
from sqlalchemy import func
from payment_api import (
    create_order_evm,
    get_evm_config,
    get_product_price_wei,
    mark_paid_testonly,
    validate_download_token_and_consume,
    verify_evm_payment,
)
from portfolio_manager import build_portfolio, write_portfolio_report
from product_factory import ProductConfig, generate_one
from promotion_dispatcher import (
    dispatch_publish,
    load_channel_config,
    save_channel_config,
)
from promotion_factory import mark_ready_to_publish
from src.key_manager import apply_keys
from scheduler_service import SchedulerService
from src.progress_tracker import get_progress
from blog_promo_bot import bot_instance

app = Flask(__name__)


@app.route("/")
def index():
    """대시보드 메인 페이지"""
    return render_template_string(Path("templates/dashboard.html").read_text(encoding="utf-8"))


@app.get("/health")
def health():
    """대시보드 헬스 체크"""
    return jsonify({"ok": True, "service": "dashboard"})


@app.route("/api/system/progress", methods=["GET"])
def system_progress():
    """현재 시스템 진행상황 조회"""
    try:
        lm = LedgerManager()
        # Use get_all_products to ensure we count everything, not just the first 100
        products = lm.get_all_products()
        total = len(products)
        published = len([p for p in products if p.get("status") in ["PUBLISHED", "PROMOTED"]])
        pending = len([p for p in products if p.get("status") == "PENDING"])
        
        # Read logs
        logs = []
        log_path = PROJECT_ROOT / "logs" / "auto_mode_daemon.log"
        if log_path.exists():
            try:
                # Read last 50 lines efficiently
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    logs = [l.strip() for l in lines[-50:]]
            except Exception:
                logs = ["Failed to read log file"]
        else:
            logs = ["Log file not found"]

        # Read daemon status
        daemon_status = {}
        status_file = PROJECT_ROOT / "data" / "daemon_status.json"
        if status_file.exists():
            try:
                daemon_status = json.loads(status_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        
        # Read current detailed progress
        current_progress = get_progress()
        
        # Financial Stats
        session = lm.get_session()
        try:
            total_revenue = session.query(func.sum(Order.amount)).filter(Order.status == 'PAID').scalar() or 0
            total_transactions = session.query(Order).filter(Order.status == 'PAID').count()
            
            recent_tx_rows = session.query(Order).filter(Order.status == 'PAID').order_by(Order.created_at.desc()).limit(5).all()
            recent_transactions = [{
                "id": tx.id,
                "product_id": tx.product_id,
                "amount": tx.amount,
                "currency": tx.currency,
                "date": tx.created_at.strftime("%Y-%m-%d %H:%M") if tx.created_at else "",
                "email": tx.customer_email
            } for tx in recent_tx_rows]
        except Exception as e:
            total_revenue = 0
            total_transactions = 0
            recent_transactions = []
            print(f"Error calculating financial stats: {e}")
        finally:
            session.close()
            
        return jsonify({
            "total_products": total,
            "published_count": published,
            "pending_count": pending,
            "total_revenue": total_revenue,
            "total_transactions": total_transactions,
            "recent_transactions": recent_transactions,
            "recent_logs": logs,
            "daemon_status": daemon_status,
            "current_progress": current_progress
        })
    except Exception as e:
        return jsonify({
            "total_products": 0,
            "published_count": 0,
            "recent_logs": [f"Error fetching stats: {str(e)}"],
            "daemon_status": {},
            "current_progress": {}
        })


@app.route("/api/products", methods=["GET"])
def list_products():
    """모든 제품 목록 및 홍보 현황 조회 (페이지네이션 지원)"""
    try:
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 10))
        
        lm = LedgerManager()
        products = lm.get_all_products()
        
        # Sort by created_at desc
        products.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        
        total_products = len(products)
        total_pages = (total_products + limit - 1) // limit
        
        # Slice for pagination
        start = (page - 1) * limit
        end = start + limit
        paginated_products = products[start:end]
        
        # Load audit report for promotion status
        audit_map = {}
        audit_file = PROJECT_ROOT / "data" / "audit_report.json"
        if audit_file.exists():
            try:
                audit_data = json.loads(audit_file.read_text(encoding="utf-8"))
                for item in audit_data.get("details", []):
                    # We are interested in promotion items
                    if "promotion_" not in item.get("type", ""):
                        continue
                    
                    pid = item.get("product_id")
                    if not pid: continue
                    
                    if pid not in audit_map:
                        audit_map[pid] = []
                    
                    channel = item.get("type").replace("promotion_", "")
                    # Normalize channel names (remove _api suffix)
                    if channel.endswith("_api"):
                        channel = channel.replace("_api", "")
                    
                    # Merge duplicate entries for the same channel
                    existing = next((x for x in audit_map[pid] if x['channel'] == channel), None)
                    if existing:
                        existing['issues'].extend(item.get("issues", []))
                    else:
                        audit_map[pid].append({
                            "channel": channel,
                            "issues": item.get("issues", [])
                        })
            except Exception:
                pass
                
        # Merge promotion data and format for frontend
        results = []
        for p in paginated_products:
            # Normalize status
            p_status = str(p.get("status", "")).strip().upper()
            
            meta = p.get("metadata", {})
            qa_status = "Pending"
            qa_details = []
            
            if p_status == "PUBLISHED":
                qa_status = "Passed"
            elif p_status == "PROMOTED":
                qa_status = "Published & Promoted"
            elif "QA2_PASSED" in p_status:
                qa_status = "Passed (Ready to Publish)"
            elif "QA1_PASSED" in p_status:
                qa_status = "Content Verified"
            elif "QA" in p_status and "FAILED" in p_status:
                qa_status = "Failed"
                # Try to extract failure reason from metadata
                if meta.get("messages"):
                    qa_details = meta.get("messages")
                elif meta.get("error"):
                    qa_details = [meta.get("error")]
            
            # If QA passed, show success messages if available
            if not qa_details and meta.get("messages"):
                 qa_details = meta.get("messages")

            # Collect promotion status from both Audit Report AND Product Metadata
            promo_list = audit_map.get(p["id"], [])
            
            # Helper to add or update
            def add_promo(channel, url=None, id_val=None):
                existing = next((x for x in promo_list if x['channel'] == channel), None)
                if existing:
                    if url: 
                        existing["url"] = url
                        existing["issues"] = [] # Clear issues if URL is confirmed
                    if id_val: 
                        existing["id"] = id_val
                        existing["issues"] = [] # Clear issues if ID is confirmed
                else:
                    entry = {"channel": channel, "issues": []}
                    if url: entry["url"] = url
                    if id_val: entry["id"] = id_val
                    promo_list.append(entry)

            # Check metadata for successful promotions
            if meta.get("wp_link"): add_promo("wordpress", url=meta.get("wp_link"))
            if meta.get("medium_url"): add_promo("medium", url=meta.get("medium_url"))
            if meta.get("tumblr_url"): add_promo("tumblr", url=meta.get("tumblr_url"))
            if meta.get("github_pages_url"): add_promo("github_pages", url=meta.get("github_pages_url"))
            if meta.get("blogger_url"): add_promo("blogger", url=meta.get("blogger_url"))
            if meta.get("reddit_url"): add_promo("reddit", url=meta.get("reddit_url"))
            
            if meta.get("x_post_id"): 
                x_id = meta.get("x_post_id")
                # Try to construct URL if it looks like a numeric ID
                x_url = f"https://x.com/i/status/{x_id}" if x_id.isdigit() else None
                add_promo("x", url=x_url, id_val=x_id)

            if meta.get("pinterest_id"): 
                pin_id = meta.get("pinterest_id")
                pin_url = f"https://www.pinterest.com/pin/{pin_id}/" if pin_id.isdigit() else None
                add_promo("pinterest", url=pin_url, id_val=pin_id)

            if meta.get("linkedin_id"): 
                li_id = meta.get("linkedin_id")
                # LinkedIn IDs are complex, often just numbers or urns. 
                # If number, likely urn:li:share:ID or urn:li:activity:ID
                li_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{li_id}/" if li_id.isdigit() else None
                add_promo("linkedin", url=li_url, id_val=li_id)
            
            if meta.get("telegram_posted") == "true": add_promo("telegram", id_val="Posted")
            if meta.get("discord_posted") == "true": add_promo("discord", id_val="Posted")

            # Fallback: if no wp_link but deployment_url exists, maybe treat deployment_url as "Site"
            # But do not label it as 'wordpress' promotion unless we are sure.
            # actually, let's keep deployment_url separate as 'live_url' in the main dict.

            results.append({
                "id": p["id"],
                "topic": p["topic"],
                "status": p_status,
                "created_at": p["created_at"],
                "published_at": meta.get("published_at"),
                "live_url": meta.get("deployment_url"),
                "price": meta.get("price_usd", 0),
                "promotions": promo_list,
                "qa_status": qa_status,
                "qa_details": qa_details,
                "preview_url": f"http://127.0.0.1:8088/outputs/{p['id']}/index.html"  # Assuming preview server port 8088
            })
            
        return jsonify({
            "products": results,
            "total": total_products,
            "page": page,
            "limit": limit,
            "total_pages": total_pages
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/system/sync_products", methods=["POST"])
def sync_products():
    """파일 시스템의 제품 정보를 원장(Ledger)과 동기화합니다."""
    try:
        lm = LedgerManager()
        outputs_dir = PROJECT_ROOT / "outputs"
        synced_count = 0
        
        if not outputs_dir.exists():
            return jsonify({"ok": False, "error": "Outputs directory not found"}), 404
            
        for item in outputs_dir.iterdir():
            if item.is_dir():
                # Check for product_schema.json or manifest.json
                schema_path = item / "product_schema.json"
                manifest_path = item / "manifest.json"
                
                product_id = item.name # Default ID is folder name if not found
                topic = "Unknown Topic"
                status = "GENERATED" # Default status
                metadata = {}
                
                # Try to load schema
                if schema_path.exists():
                    try:
                        schema = json.loads(schema_path.read_text(encoding="utf-8"))
                        product_id = schema.get("id", product_id)
                        topic = schema.get("topic", topic)
                    except:
                        pass
                
                # Try to load manifest (better source)
                if manifest_path.exists():
                    try:
                        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                        product_id = manifest.get("id", product_id)
                        topic = manifest.get("topic", topic)
                        status = manifest.get("status", status)
                        metadata.update(manifest)
                    except:
                        pass
                
                # Infer status from files
                if (item / "package.zip").exists():
                    status = "PACKAGED"
                if (item / "final_publish_info.json").exists():
                    status = "PUBLISHED"
                    try:
                        pub_info = json.loads((item / "final_publish_info.json").read_text(encoding="utf-8"))
                        metadata.update(pub_info)
                        metadata["deployment_url"] = pub_info.get("url")
                    except:
                        pass
                
                # Update Ledger
                try:
                    # Check if exists
                    existing = lm.get_product(product_id)
                    if not existing:
                        lm.create_product(product_id, topic, metadata)
                        lm.update_product_status(product_id, status, metadata=metadata)
                        synced_count += 1
                    else:
                        # Update status if advanced
                        if status == "PUBLISHED" and existing.get("status") != "PUBLISHED":
                            lm.update_product_status(product_id, status, metadata=metadata)
                            synced_count += 1
                except Exception as e:
                    print(f"Failed to sync {product_id}: {e}")
                    
        return jsonify({"ok": True, "synced": synced_count})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/system/control", methods=["POST", "GET"])
def system_control():
    """서버 프로세스 제어 (POST: 제어, GET: 현재 포트 점유 프로세스 확인)"""
    if request.method == "GET":
        return jsonify({"info": "Use POST to control servers"})

    data = request.json or {}
    name = data.get("name")
    action = data.get("action")
    
    if not name or name not in ["payment", "preview", "daemon"]:
        return jsonify({"ok": False, "error": "Invalid name"}), 400
    
    if action == "start":
        if name == "payment":
            _stop_process("payment")
            if _is_windows():
                _kill_port(5000)
            _start_process("payment", [sys.executable, "backend/payment_server.py"])
        elif name == "preview":
            _stop_process("preview")
            if _is_windows():
                _kill_port(8090)
            _start_process("preview", [sys.executable, "preview_server.py"])
        elif name == "daemon":
            # 데몬은 기존 PID 확인 후 종료하고 시작
            sf = PROJECT_ROOT / "data" / "daemon_status.json"
            if sf.exists():
                try:
                    ds = json.loads(sf.read_text(encoding="utf-8"))
                    old_pid = ds.get("pid")
                    if old_pid:
                        if _is_windows():
                            subprocess.run(["taskkill", "/PID", str(old_pid), "/F", "/T"], capture_output=True)
                        else:
                            import signal
                            os.kill(old_pid, signal.SIGTERM)
                except:
                    pass
            _start_process("daemon", [sys.executable, "auto_mode_daemon.py", "--interval", "3600", "--batch", "1", "--deploy", "1", "--publish", "1"])
        
        # 시작 후 약간의 대기시간을 주어 서버가 포트를 점유할 시간을 줍니다.
        time.sleep(1.5)
        return jsonify({"ok": True, "action": "start"})
    
    elif action == "stop":
        if name == "daemon":
            sf = PROJECT_ROOT / "data" / "daemon_status.json"
            if sf.exists():
                try:
                    ds = json.loads(sf.read_text(encoding="utf-8"))
                    old_pid = ds.get("pid")
                    if old_pid:
                        if _is_windows():
                            subprocess.run(["taskkill", "/PID", str(old_pid), "/F", "/T"], capture_output=True)
                        else:
                            import signal
                            os.kill(old_pid, signal.SIGTERM)
                    # 상태 업데이트
                    ds["status"] = "stopped"
                    sf.write_text(json.dumps(ds, indent=2), encoding="utf-8")
                except:
                    pass
            return jsonify({"ok": True, "action": "stop"})
            
        _stop_process(name)
        if _is_windows():
            _kill_port(5000 if name == "payment" else 8088)
        return jsonify({"ok": True, "action": "stop"})
    
    return jsonify({"ok": False, "error": "Invalid action"}), 400


def _kill_port(port: int):
    """특정 포트를 사용하는 프로세스 강제 종료 (Windows)"""
    if not _is_windows():
        return
    try:
        # 정확한 포트 매칭을 위해 :port 뒤에 공백을 추가하거나 정규식 사용 고려
        # netstat -ano | findstr LISTENING | findstr :<port>
        cmd = f"netstat -ano"
        # Windows CMD output is often cp949
        output = subprocess.check_output(cmd, shell=True).decode("cp949", errors="ignore")
        for line in output.splitlines():
            if "LISTENING" in line and f":{port}" in line:
                parts = line.strip().split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    if pid and pid != "0":
                        # 내 프로세스(대시보드)는 죽이지 않도록 보호
                        if int(pid) == os.getpid():
                            continue
                        subprocess.run(["taskkill", "/PID", pid, "/F", "/T"], capture_output=True)
    except Exception:
        pass


def _get_channel_status() -> Dict[str, bool]:
    """secrets.json을 기반으로 각 채널 설정 여부를 확인합니다."""
    secrets = _read_json(SECRETS_PATH, {})
    status = {}
    
    # Helper to check nested or flat
    def check(keys, section=None):
        if section and section in secrets:
            if isinstance(secrets[section], dict):
                if all(k in secrets[section] for k in keys):
                    return True
        return all(secrets.get(k) for k in keys)

    status['wordpress'] = check(['api_url', 'username', 'password'], 'wordpress') or \
                          (secrets.get('WP_API_URL') and secrets.get('WP_USER') and secrets.get('WP_PASSWORD'))
    
    status['medium'] = check(['token'], 'medium') or bool(secrets.get('MEDIUM_TOKEN'))
    
    status['tumblr'] = check(['consumer_key', 'consumer_secret', 'oauth_token', 'oauth_token_secret'], 'tumblr') or \
                       (secrets.get('TUMBLR_CONSUMER_KEY') and secrets.get('TUMBLR_CONSUMER_SECRET'))
                       
    status['blogger'] = check(['client_id', 'client_secret'], 'blogger') or \
                        (secrets.get('BLOGGER_CLIENT_ID') and secrets.get('BLOGGER_CLIENT_SECRET'))
                        
    status['github_pages'] = check(['token', 'repo_url'], 'github') or \
                             (secrets.get('GITHUB_TOKEN') and secrets.get('GITHUB_REPO_URL'))
                             
    status['x'] = check(['api_key', 'api_secret', 'access_token', 'access_token_secret'], 'twitter') or \
                  (secrets.get('TWITTER_API_KEY') and secrets.get('TWITTER_ACCESS_TOKEN'))
                  
    status['reddit'] = check(['client_id', 'client_secret', 'username', 'password'], 'reddit') or \
                       (secrets.get('REDDIT_CLIENT_ID') and secrets.get('REDDIT_USERNAME'))
                       
    status['pinterest'] = check(['access_token'], 'pinterest') or bool(secrets.get('PINTEREST_ACCESS_TOKEN'))
    
    status['linkedin'] = check(['access_token'], 'linkedin') or bool(secrets.get('LINKEDIN_ACCESS_TOKEN'))
    
    status['discord'] = check(['webhook_url'], 'discord') or bool(secrets.get('DISCORD_WEBHOOK_URL'))
    
    status['telegram'] = check(['bot_token', 'chat_id'], 'telegram') or \
                         (secrets.get('TELEGRAM_BOT_TOKEN') and secrets.get('TELEGRAM_CHAT_ID'))
                         
    status['youtube_shorts'] = check(['client_id', 'client_secret', 'refresh_token'], 'youtube') or \
                               (secrets.get('YOUTUBE_CLIENT_ID') and secrets.get('YOUTUBE_CLIENT_SECRET') and secrets.get('YOUTUBE_REFRESH_TOKEN'))
                               
    status['instagram'] = secrets.get('INSTAGRAM_ACCESS_TOKEN') or True # Simulation enabled by default
    status['tiktok'] = secrets.get('TIKTOK_ACCESS_TOKEN') or True # Simulation enabled by default

    return status

@app.get("/api/system/status")
def system_status():
    """전체 시스템 서비스 상태 확인"""
    import requests
    pids = _pids()
    services = {
        "payment": {"port": 5000, "url": "http://127.0.0.1:5000/health"},
        "preview": {"port": 8088, "url": "http://127.0.0.1:8088/health"},
        "daemon": {"status_file": str(PROJECT_ROOT / "data" / "daemon_status.json")},
    }
    
    results = {}
    pids = _pids() # 최신 PIDs 로드
    for name, cfg in services.items():
        if name == "daemon":
            # 데몬 상태 확인 (파일 기반)
            daemon_status = {}
            sf = Path(cfg["status_file"])
            if sf.exists():
                try:
                    daemon_status = json.loads(sf.read_text(encoding="utf-8"))
                except:
                    pass
            
            # 실제 PID 확인
            running = False
            pid = daemon_status.get("pid")
            if pid:
                if _is_windows():
                    import ctypes
                    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
                    if handle:
                        ctypes.windll.kernel32.CloseHandle(handle)
                        running = True
                else:
                    try:
                        os.kill(pid, 0)
                        running = True
                    except OSError:
                        pass
            
            results[name] = {
                "running": running,
                "alive": running, # 데몬은 헬스체크가 따로 없으므로 running과 동일하게 취급
                "pid": pid if running else None,
                "details": daemon_status
            }
            continue

        # PID 파일 기반 실행 여부 확인
        running = name in pids
        alive = False
        
        # 실제 프로세스가 살아있는지 OS 수준에서 한 번 더 확인 (PID 존재 여부)
        if running:
            pid = pids[name].get("pid")
            if pid:
                if _is_windows():
                    # Windows에서 PID 존재 확인
                    import ctypes
                    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
                    if handle:
                        ctypes.windll.kernel32.CloseHandle(handle)
                    else:
                        running = False
                else:
                    try:
                        os.kill(pid, 0)
                    except OSError:
                        running = False

        # 헬스체크는 running 여부와 상관없이 시도 (좀 더 관대하게 상태 표시)
        try:
            # 헬스체크 엔드포인트 호출 시도
            r = requests.get(cfg["url"], timeout=2)
            alive = r.status_code == 200
            if alive:
                running = True # 헬스체크 성공하면 살아있는 것으로 간주
        except Exception as e:
            alive = False
        
        results[name] = {
            "running": running,
            "alive": alive,
            "pid": pids.get(name, {}).get("pid") if running else None
        }
    
    # Add Bot Status
    results["bot"] = {
        "running": bot_instance.is_running(),
        "alive": bot_instance.is_running(),
        "logs": bot_instance.get_logs()[:5] # Latest 5 logs
    }

    # Add Channel Status
    results["channels"] = _get_channel_status()
        
    return jsonify(results)

@app.route("/api/bot/control", methods=["POST"])
def api_bot_control():
    """Bot 제어 (start/stop)"""
    data = request.json or {}
    action = data.get("action")
    
    if action == "start":
        bot_instance.start()
        return jsonify({"ok": True, "status": "started"})
    elif action == "stop":
        bot_instance.stop()
        return jsonify({"ok": True, "status": "stopped"})
    else:
        return jsonify({"ok": False, "error": "Invalid action"}), 400

@app.get("/api/bot/logs")
def bot_logs():
    """Bot 로그 조회"""
    return jsonify({
        "logs": bot_instance.get_logs(),
        "running": bot_instance.is_running(),
        "connections": bot_instance.get_connection_status()
    })



PROJECT_ROOT = Path(__file__).resolve().parent
# Startup key application (Sync secrets.json and os.environ)
apply_keys(PROJECT_ROOT, write=False, inject=True)

SCHED = SchedulerService(PROJECT_ROOT)

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
PIDS_PATH = DATA_DIR / "pids.json"
AUTO_MODE_STATUS_PATH = DATA_DIR / "auto_mode_status.json"
SECRETS_PATH = DATA_DIR / "secrets.json"
DEFAULT_DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8099"))


def _atomic_write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(
            json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except Exception:
        return # writing failed, abort

    # Retry loop for Windows file locking
    max_retries = 20
    for i in range(max_retries):
        try:
            if path.exists():
                os.replace(tmp, path)
            else:
                os.rename(tmp, path)
            return
        except PermissionError:
            if i < max_retries - 1:
                time.sleep(0.5)
            else:
                # Force delete and move if possible, or just log error
                try:
                    if path.exists():
                        os.remove(path)
                    os.rename(tmp, path)
                except Exception:
                    pass
        except Exception:
            pass
            
    # Cleanup tmp if failed
    try:
        if tmp.exists():
            os.remove(tmp)
    except:
        pass


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def _load_secrets() -> Dict[str, Any]:
    return _read_json(SECRETS_PATH, {})

def _save_secrets(data: Dict[str, Any]) -> None:
    _atomic_write_json(SECRETS_PATH, data)
    for k, v in data.items():
        if isinstance(v, str):
            os.environ[k] = v
    try:
        import importlib
        from src import config as _cfg
        importlib.reload(_cfg)
    except Exception:
        pass


def _pids() -> Dict[str, Any]:
    return _read_json(PIDS_PATH, {})


def _set_pid(name: str, pid: int, cmd: List[str], log_file: str) -> None:
    p = _pids()
    p[name] = {
        "pid": int(pid),
        "cmd": cmd,
        "log_file": log_file,
        "started_at": _utc_iso(),
    }
    _atomic_write_json(PIDS_PATH, p)


def _clear_pid(name: str) -> None:
    p = _pids()
    if name in p:
        del p[name]
        _atomic_write_json(PIDS_PATH, p)


def _utc_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _is_windows() -> bool:
    return os.name == "nt"


def _kill_pid(pid: int) -> bool:
    """프로세스 종료(Windows/Unix 대응)."""
    try:
        if _is_windows():
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
            )
            return True
        else:
            os.kill(pid, 15)
            return True
    except Exception:
        return False


def _start_process(name: str, cmd: List[str]) -> Dict[str, Any]:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    log_path = LOGS_DIR / f"{name}.log"
    # 로그 파일을 새로 쓰기 모드로 열어 이전 오류 로그를 초기화합니다.
    f = log_path.open("w", encoding="utf-8")
    try:
        # 현재 환경변수 복사 및 Flask/Werkzeug 관련 제어 변수 제거
        # (부모의 디버그 모드 변수가 자식에게 영향을 주어 WinError 10038 유발 방지)
        env = os.environ.copy()
        env.pop("WERKZEUG_RUN_MAIN", None)
        env.pop("WERKZEUG_SERVER_FD", None)
        
        p = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=f,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            shell=False,
            env=env,
            close_fds=True # Windows에서 핸들 상속 방지
        )
        _set_pid(name=name, pid=p.pid, cmd=cmd, log_file=str(log_path))
        return {"ok": True, "pid": p.pid, "log_file": str(log_path)}
    except Exception as e:
        f.close()
        return {"ok": False, "error": str(e)}


def _stop_process(name: str) -> Dict[str, Any]:
    info = _pids().get(name)
    if not info:
        return {"ok": True, "status": "not_running"}
    pid = int(info.get("pid", 0))
    ok = _kill_pid(pid)
    _clear_pid(name)
    return {"ok": ok, "pid": pid}


def _tail_log(path: Path, n: int = 200) -> str:
    if not path.exists():
        return "(log not found)"
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        return "\n".join(lines[-max(1, int(n)) :])
    except Exception:
        return "(failed to read log)"


def _list_products() -> List[Dict[str, Any]]:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    items: List[Dict[str, Any]] = []
    ledger = None
    try:
        import sys as _sys
        if str(PROJECT_ROOT) not in _sys.path:
            _sys.path.insert(0, str(PROJECT_ROOT))
        from src.ledger_manager import LedgerManager  # type: ignore
        ledger = LedgerManager()
    except Exception:
        ledger = None

    # 1. 원장(Ledger)에 등록된 모든 상품을 기본 목록으로 가져옵니다.
    ledger_products = []
    if ledger:
        try:
            # list_products는 기본적으로 최신순 정렬되어 있음
            ledger_products = ledger.list_products(limit=1000)
        except Exception as e:
            print(f"DEBUG: Failed to list products from ledger: {e}")

    # 2. 원장 상품 정보를 아이템 리스트에 추가
    ledger_ids = set()
    for prod in ledger_products:
        pid = prod.get("id")
        if not pid:
            continue
        ledger_ids.add(pid)
        
        d = OUTPUTS_DIR / pid
        status = str(prod.get("status") or "")
        meta = prod.get("metadata") or {}
        deployment_url = str(meta.get("deployment_url") or "")
        topic = str(prod.get("topic") or "")
        title = str(meta.get("title") or topic or pid)
        
        # Promotion Status Check
        promo_channels = []
        promo_file = d / "promotions" / "publish_results.json"
        if promo_file.exists():
            try:
                pr = json.loads(promo_file.read_text(encoding="utf-8"))
                dr = pr.get("dispatch_results", {})
                for ch, res in dr.items():
                    if res.get("ok"):
                        promo_channels.append(ch)
            except:
                pass

        item = {
            "product_id": pid,
            "topic": topic,
            "title": title,
            "created_at": str(prod.get("created_at") or ""),
            "has_landing": (d / "index.html").exists(),
            "has_package": (d / "package.zip").exists(),
            "status": status,
            "deployment_url": deployment_url,
            "price_wei": get_product_price_wei(PROJECT_ROOT, pid),
            "promo_channels": promo_channels,
        }
        items.append(item)

    # 3. 원장에는 없지만 outputs 폴더에만 있는 상품들도 추가 (하위 호환성 및 누락 방지)
    for d in OUTPUTS_DIR.iterdir():
        if not d.is_dir() or d.name in ledger_ids:
            continue
        
        pid = d.name
        
        # Promotion Status Check (Local)
        promo_channels = []
        promo_file = d / "promotions" / "publish_results.json"
        if promo_file.exists():
            try:
                pr = json.loads(promo_file.read_text(encoding="utf-8"))
                dr = pr.get("dispatch_results", {})
                for ch, res in dr.items():
                    if res.get("ok"):
                        promo_channels.append(ch)
            except:
                pass

        item = {
            "product_id": pid,
            "created_at": time.strftime(
                "%Y-%m-%d %H:%M:%S", time.gmtime(d.stat().st_mtime)
            ),
            "has_landing": (d / "index.html").exists(),
            "has_package": (d / "package.zip").exists(),
            "status": "LOCAL_ONLY",
            "deployment_url": "",
            "price_wei": get_product_price_wei(PROJECT_ROOT, pid),
            "promo_channels": promo_channels,
        }
        items.append(item)
        
    return items


def _orders_store() -> FileOrderStore:
    return FileOrderStore(DATA_DIR)


TEMPLATE = """<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\"/>
  <link rel=\"icon\" href=\"data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><rect width=%22100%22 height=%22100%22 fill=%22%2322c55e%22></rect></svg>\">
  <title>MetaPassiveIncome Dashboard</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; }
    .grid { display:grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .card { border:1px solid #ddd; border-radius:12px; padding:14px; }
    button { padding:8px 12px; border-radius:10px; border:1px solid #999; cursor:pointer; }
    input { padding:8px; border-radius:10px; border:1px solid #bbb; width: 100%; box-sizing: border-box; }
    .muted { color:#666; font-size: 13px; }
    .badge { padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; }
    .badge-paid { background: #dcfce7; color: #166534; }
    .badge-pending { background: #fef9c3; color: #854d0e; }
    .badge-published { background: #dbeafe; color: #1e40af; }
    .badge-promoted { background: #dbeafe; color: #1e40af; }
    .badge-waiting_for_deployment { background: #fef3c7; color: #92400e; }
    .badge-packaged { background: #f3e8ff; color: #6b21a8; }
    .badge-error { background: #fee2e2; color: #991b1b; }
    .badge-unknown { background: #f3f4f6; color: #374151; }
    .status-bar { display: flex; gap: 16px; background: #f8fafc; padding: 12px; border-radius: 8px; margin-bottom: 16px; border: 1px solid #e2e8f0; }
    .status-item { display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 600; }
    .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
    .dot-online { background: #22c55e; box-shadow: 0 0 8px #22c55e; }
    .dot-offline { background: #ef4444; }
    .dot-starting { background: #f59e0b; }
    code { background:#f3f4f6; padding:2px 6px; border-radius:6px; }
    table { width:100%; border-collapse: collapse; }
    th, td { border-bottom:1px solid #eee; padding:8px; text-align:left; font-size: 13px; }
    a { color:#2563eb; }
    pre { white-space: pre-wrap; background:#0b1220; color:#e7eef7; padding:10px; border-radius:10px; max-height:260px; overflow:auto; }
  </style>
</head>
<body>
  <h1>MetaPassiveIncome Dashboard</h1>
  
  <div class="status-bar" id="systemStatusBar">
    <div class="status-item">System Status:</div>
    <div class="status-item" id="status-payment"><span class="dot dot-offline"></span> Payment Server</div>
    <div class="status-item" id="status-preview"><span class="dot dot-offline"></span> Preview Server</div>
    <div class="status-item" id="status-autopilot"><span class="dot dot-offline"></span> AutoPilot</div>
    <div class="status-item" id="status-vercel"><span class="badge badge-published">{{health.vercel_info}}</span></div>
  </div>

  <div class="card" style="margin-bottom:16px; background: #f8fafc; border-color: #e2e8f0;">
    <h3>Channel Configuration Status</h3>
    <div style="display:flex; flex-wrap:wrap; gap:10px;">
      {% for ch, active in channel_status.items() %}
      <div style="background:white; padding:5px 10px; border-radius:6px; border:1px solid #ddd; font-size:13px; display:flex; align-items:center; gap:5px;">
        <span>{{ch|capitalize}}</span>
        {% if active %}
          <span style="color:#16a34a;">✅</span>
        {% else %}
          <span style="color:#dc2626;">❌</span>
        {% endif %}
      </div>
      {% endfor %}
    </div>
    <div class="muted" style="margin-top:5px; font-size:11px;">
      Red X (❌) means credentials are missing in secrets.json. Run <code>SETUP_CHANNELS.bat</code> to configure.
    </div>
  </div>

  <div class="card" id="bot-card" style="margin-bottom:16px; background: #fff1f2; border-color: #fecdd3;">
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <h3 style="margin:0; color: #be123c;">Blog Promotion Bot (Auto-Pilot)</h3>
        <div style="display:flex; gap:10px; align-items:center;">
            <div id="bot-connections" style="display:flex; gap:5px; font-size:11px;"></div>
            <div id="bot-status-indicator" class="badge badge-unknown" style="font-size:14px;">Unknown</div>
        </div>
    </div>
    <div style="margin-top:10px; display:flex; gap:10px;">
        <button onclick="controlBot('start')" style="background:#f43f5e; color:white; border:none; font-weight:bold;">Start Bot</button>
        <button onclick="controlBot('stop')" style="background:#881337; color:white; border:none; font-weight:bold;">Stop Bot</button>
    </div>
    <div style="margin-top:10px;">
        <div class="muted">Recent Logs (Auto-refresh):</div>
        <pre id="bot-logs" style="height:150px; font-size:11px; margin-top:5px; background:#1e1b4b; color:#e0e7ff;">Loading...</pre>
    </div>
  </div>

  <script>
    async function controlBot(action) {
        try {
            const r = await fetch('/api/bot/control', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action})
            });
            if (!r.ok) throw new Error('Server returned ' + r.status);
            await r.json();
            updateBotStatus();
        } catch(e) {
            console.error('Control Bot Error:', e);
            alert('Failed to control bot: ' + e.message);
        }
    }

    async function updateBotStatus() {
        try {
            const r = await fetch('/api/bot/logs');
            if (!r.ok) return; // Skip if server error
            const data = await r.json();
            
            const statusEl = document.getElementById('bot-status-indicator');
            if (data.running) {
                statusEl.textContent = 'RUNNING';
                statusEl.style.background = '#22c55e';
                statusEl.style.color = 'white';
            } else {
                statusEl.textContent = 'STOPPED';
                statusEl.style.background = '#ef4444';
                statusEl.style.color = 'white';
            }
            
            // Connection Status
            const connEl = document.getElementById('bot-connections');
            if (connEl && data.connections) {
                let html = '';
                for (const [platform, connected] of Object.entries(data.connections)) {
                    const color = connected ? '#16a34a' : '#dc2626';
                    const icon = connected ? '✅' : '❌';
                    html += `<span style="color:${color}; border:1px solid ${color}; padding:1px 4px; border-radius:4px;">${platform} ${icon}</span>`;
                }
                connEl.innerHTML = html;
            }
            
            const logsEl = document.getElementById('bot-logs');
            if (data.logs && data.logs.length > 0) {
                logsEl.textContent = data.logs.join('\\n');
            } else {
                logsEl.textContent = '(No logs yet)';
            }
        } catch(e) {
            console.error(e);
        }
    }
    
    setInterval(updateBotStatus, 3000);
    updateBotStatus();
  </script>

  <div class="card" id="progress-card" style="display:none; background: #f0f9ff; border-color: #bae6fd; margin-bottom: 16px;">
    <h3 style="margin-top:0; color: #0369a1;">Real-time Activity</h3>
    <div style="display:flex; align-items:center; gap:15px;">
        <div style="flex:1;">
            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                <span id="prog-task" style="font-weight:bold; color:#0c4a6e;">Idle</span>
                <span id="prog-percent" style="font-weight:bold; color:#0369a1;">0%</span>
            </div>
            <div style="background:#e0f2fe; height:10px; border-radius:5px; overflow:hidden;">
                <div id="prog-bar" style="width:0%; height:100%; background:#0ea5e9; transition: width 0.5s ease;"></div>
            </div>
            <div id="prog-status" style="margin-top:5px; font-size:13px; color:#0284c7;">Waiting...</div>
            <div id="prog-details" style="font-size:11px; color:#7dd3fc; margin-top:2px;"></div>
        </div>
        <div style="text-align:right;">
             <span id="prog-time" style="font-size:11px; color:#94a3b8;"></span>
        </div>
    </div>
  </div>

  <div class="card" style="margin-bottom:16px; background: #f0fdf4; border-color: #bbf7d0;">
    <h3>System Health & Sales Summary</h3>
    <div style="display:grid; grid-template-columns: repeat(6, 1fr); gap: 10px; text-align: center;">
      <div><div class="muted">Total Products</div><div style="font-size: 20px; font-weight: bold;">{{health.stats.total}}</div></div>
      <div><div class="muted">Published</div><div style="font-size: 20px; font-weight: bold; color: #16a34a;">{{health.stats.published}}</div></div>
      <div><div class="muted">Recovery Needed</div><div style="font-size: 20px; font-weight: bold; color: #dc2626;">{{health.stats.failed}}</div></div>
      <div><div class="muted">Waiting Deployment</div><div style="font-size: 20px; font-weight: bold; color: #d97706;">{{health.stats.waiting}}</div></div>
      <div style="background: #ecfdf5; border-radius: 8px; padding: 5px;"><div class="muted">Total Sales</div><div style="font-size: 20px; font-weight: bold; color: #059669;">{{perf_report.summary.total_paid if perf_report.summary else health.stats.total_sales}}</div></div>
      <div style="background: #ecfdf5; border-radius: 8px; padding: 5px;"><div class="muted">Revenue</div><div style="font-size: 20px; font-weight: bold; color: #059669;">${{ "%.2f"|format(perf_report.summary.estimated_revenue if perf_report.summary else health.stats.revenue) }}</div></div>
    </div>
    {% if perf_report.summary %}
    <div style="margin-top: 15px; padding-top: 10px; border-top: 1px dashed #bbf7d0; display: flex; gap: 20px; font-size: 13px;">
      <span><b>Conversion Rate:</b> {{ perf_report.summary.conversion_rate }}%</span>
      <span><b>Total Orders:</b> {{ perf_report.summary.total_orders }}</span>
      <span><b>Last Generated:</b> {{ perf_report.generated_at }}</span>
    </div>
    {% endif %}
    <div class="muted" style="margin-top: 10px; font-size: 11px;">Last Health Check: {{health.timestamp}}</div>
  </div>

  {% if perf_report.daily_trends %}
  <div class="card" style="margin-bottom:16px; background: #fafafa; border-color: #e5e7eb;">
    <h3>Sales Performance Trends (Last 30 Days)</h3>
    <div style="height: 120px; display: flex; align-items: flex-end; gap: 4px; padding: 10px 0;">
      {% set max_count = 1 %}
      {% for date, stats in perf_report.daily_trends.items()|sort %}
        {% if stats.count > max_count %}{% set max_count = stats.count %}{% endif %}
      {% endfor %}
      
      {% for date, stats in perf_report.daily_trends.items()|sort %}
        <div title="{{date}}: {{stats.count}} sales (${{stats.revenue}})" 
             style="flex: 1; background: {% if stats.count > 0 %}#22c55e{% else %}#e5e7eb{% endif %}; 
                    height: {{ (stats.count / max_count * 100)|round|int if stats.count > 0 else 5 }}%; 
                    border-radius: 2px;"></div>
      {% endfor %}
    </div>
    <div style="display: flex; justify-content: space-between; font-size: 10px; color: #94a3b8; margin-top: 5px;">
      <span>{{ (perf_report.daily_trends.items()|sort)[0][0] }}</span>
      <span>Daily Sales Volume (Green = Sales, Grey = No Sales)</span>
      <span>{{ (perf_report.daily_trends.items()|sort)[-1][0] }}</span>
    </div>
  </div>
  {% endif %}

  {% if perf_report.top_products %}
  <div class="card" style="margin-bottom:16px; background: #fdf2f8; border-color: #fbcfe8;">
    <h3>Top Performing Products</h3>
    <table style="background: white; border-radius: 8px;">
      <thead>
        <tr><th>Product ID</th><th style="text-align: right;">Sales Count</th></tr>
      </thead>
      <tbody>
        {% for tp in perf_report.top_products %}
        <tr>
          <td><code>{{ tp.product_id }}</code></td>
          <td style="text-align: right; font-weight: bold; color: #be185d;">{{ tp.sales }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}

  <div class="card" style="margin-bottom:16px; background: #fffbeb; border-color: #fcd34d;">
    <h3>Pipeline Recovery & Vercel Reset</h3>
    <p class="muted">배포 한도 초과(402) 또는 속도 제한(429)으로 실패한 제품들을 복구합니다.</p>
    <div style="display:flex; gap:10px;">
      <a href="/action/run_recovery"><button style="background:#fbbf24; border:none; color:white; font-weight:bold;">Run Recovery Script</button></a>
      <a href="/action/redeploy_waiting"><button style="background:#f59e0b; border:none; color:white; font-weight:bold;">Redeploy All Waiting</button></a>
      <a href="/action/check_vercel"><button>Check Vercel Reset Status</button></a>
      <a href="/action/vercel_cleanup"><button style="background:#ef4444; border:none; color:white; font-weight:bold;">Vercel Project Cleanup</button></a>
    </div>
  </div>

  <div class="card" style="margin-bottom:16px; background: #f0f9ff; border-color: #bae6fd;">
    <h3>Audit Bot Report</h3>
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <p class="muted">시스템 상태 및 홍보 발행 상태를 검수합니다. (Last Audit: {{audit_report.last_audit or 'N/A'}})</p>
      <div style="display:flex; gap:10px;">
        <a href="/action/run_perf_analysis"><button style="background:#10b981; border:none; color:white; font-weight:bold;">Refresh Performance Report</button></a>
        <a href="/action/run_audit"><button style="background:#0ea5e9; border:none; color:white; font-weight:bold;">Run Audit Now</button></a>
      </div>
    </div>
    <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap: 10px; text-align: center; margin-top: 10px;">
      <div style="background: white; padding: 8px; border-radius: 8px; border: 1px solid #e0f2fe;">
        <div class="muted">Healthy Products</div>
        <div style="font-size: 18px; font-weight: bold; color: #0369a1;">{{audit_report.summary.healthy_products or 0}} / {{audit_report.summary.total_products or 0}}</div>
      </div>
      <div style="background: white; padding: 8px; border-radius: 8px; border: 1px solid #e0f2fe;">
        <div class="muted">Broken Products</div>
        <div style="font-size: 18px; font-weight: bold; color: #dc2626;">{{audit_report.summary.broken_products or 0}}</div>
      </div>
      <div style="background: white; padding: 8px; border-radius: 8px; border: 1px solid #e0f2fe;">
        <div class="muted">Healthy Promos</div>
        <div style="font-size: 18px; font-weight: bold; color: #0369a1;">{{audit_report.summary.healthy_promotions or 0}} / {{audit_report.summary.total_promotions or 0}}</div>
      </div>
      <div style="background: white; padding: 8px; border-radius: 8px; border: 1px solid #e0f2fe;">
        <div class="muted">Broken Promos</div>
        <div style="font-size: 18px; font-weight: bold; color: #dc2626;">{{audit_report.summary.broken_promotions or 0}}</div>
      </div>
    </div>
    {% if audit_report.details %}
    <details style="margin-top: 10px;">
      <summary style="cursor: pointer; color: #0369a1; font-size: 13px;">View Audit Details</summary>
      <div style="max-height: 200px; overflow-y: auto; margin-top: 5px; font-size: 12px; background: white; padding: 10px; border-radius: 8px;">
        {% for detail in audit_report.details %}
          {% if detail.issues %}
            <div style="margin-bottom: 5px; color: #991b1b;">
              <b>{{detail.product_id}}</b> ({{detail.type}}): {{detail.issues|join(', ')}}
            </div>
          {% endif %}
        {% endfor %}
        {% if not audit_report.summary.broken_products and not audit_report.summary.broken_promotions %}
          <div style="color: #166534;">All systems are healthy.</div>
        {% endif %}
      </div>
    </details>
    {% endif %}
  </div>

  <div style="padding:10px;border:1px solid #ddd;border-radius:8px;margin:10px 0;">
    <b>One-click startup</b><br/>
    <a href="/download/startup_bundle">Download START_AUTO (dashboard + payment + preview + auto-mode)</a>
  </div>

  <div class=\"muted\">Project root: <code>{{root}}</code></div>

  <div class=\"grid\">
    <div class=\"card\">
      <h2>Server Controls</h2>
      <div class=\"muted\">Payment: http://127.0.0.1:5000 · Preview: http://127.0.0.1:8090/_list</div>
      <p>
        <a href=\"/action/start_payment\"><button>Start Payment Server</button></a>
        <a href=\"/action/stop_payment\"><button>Stop Payment Server</button></a>
      </p>
      <p>
        <a href=\"/action/start_preview\"><button>Start Preview Server</button></a>
        <a href=\"/action/stop_preview\"><button>Stop Preview Server</button></a>
      </p>
      <div class=\"muted\">Running: {{pids}}</div>
    </div>

    <div class=\"card\">
      <h2>Pipeline Controls</h2>
      <div class="muted">auto_pilot은 1회 실행(배치) / Auto Mode는 주기적으로 자동 반복합니다.</div>
      <form method=\"post\" action=\"/action/run_autopilot\">
        <label class=\"muted\">Batch N</label>
        <input name=\"batch\" value=\"1\" />
        <label class=\"muted\">Optional topic (blank = auto)</label>
        <input name=\"topic\" value=\"\" />
        <p><button type=\"submit\">Run auto_pilot</button></p>
      </form>

      <form method=\"post\" action=\"/action/rebuild_product\">
        <label class=\"muted\">Rebuild by product_id</label>
        <input name=\"product_id\" value=\"\" />
        <label class=\"muted\">Topic (required)</label>
        <input name=\"topic\" value=\"\" />
        <p><button type=\"submit\">Rebuild Product</button></p>
      </form>
    </div>
  </div>

  <div class="card" style="margin-top:16px">
    <h2>System Administration</h2>
    <div style="display:flex; gap:10px;">
      <a href="/action/apply_keys" title="secrets.json 설정을 .env 및 시스템 환경변수에 즉시 반영합니다.">
        <button style="background:#f8fafc;">Sync System Environment (apply_keys)</button>
      </a>
      <a href="/action/refresh_dashboard" title="대시보드 데이터를 새로고침합니다.">
        <button style="background:#f8fafc;">Refresh Dashboard Data</button>
      </a>
    </div>

    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="card" style="background: {% if category=='success' %}#f0fdf4{% else %}#fef2f2{% endif %}; border-color: {% if category=='success' %}#bbf7d0{% else %}#fecaca{% endif %}; margin-top: 10px;">
            <b style="color: {% if category=='success' %}#16a34a{% else %}#dc2626{% endif %};">{{ category | upper }}:</b> {{ message }}
          </div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    <div class="muted" style="margin-top:8px;">
      시스템 설정을 변경한 후 'Sync System Environment'를 클릭하면 즉시 적용됩니다.
    </div>
  </div>

  <div class="card" style="margin-top:16px">
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <h2>Products ({{total_products_count}})</h2>
      <div class="pagination" style="display:flex; gap:5px; align-items:center;">
        {% if page > 1 %}
          <a href="/?page={{page-1}}"><button type="button">&laquo; Prev</button></a>
        {% endif %}
        <span class="muted">Page {{page}} of {{total_pages}}</span>
        {% if page < total_pages %}
          <a href="/?page={{page+1}}"><button type="button">Next &raquo;</button></a>
        {% endif %}
      </div>
    </div>
    <form method=\"post\" action=\"/action/bulk_products\">
      <table>
        <thead>
          <tr>
            <th><input type="checkbox" onclick="for(const cb of document.querySelectorAll('.bulk-select')) cb.checked=this.checked"/></th>
            <th>product_id</th>
            <th>price</th>
            <th>created_at(approx)</th>
            <th>status</th>
            <th>links</th>
            <th>live</th>
            <th>actions</th>
          </tr>
        </thead>
        <tbody>
          {% for p in products %}
          <tr>
            <td><input class="bulk-select" type="checkbox" name="product_id" value="{{p.product_id}}"/></td>
            <td><code>{{p.product_id}}</code></td>
            <td style="font-weight:bold; color:#059669;">{{ (p.price_wei / 1e18)|round(4) }} ETH</td>
            <td>{{p.created_at}}</td>
            <td>
              <span class="badge badge-{{(p.status or 'N/A').lower() if (p.status or '').lower() in ['paid','pending','published','packaged','error','waiting_for_deployment','promoted','qa_approved'] else 'unknown'}}">{{p.status or 'N/A'}}</span>
            </td>
            <td>
              {% if p.has_landing %}
                <a href=\"/product/{{p.product_id}}/\" target=\"_blank\">preview</a>
              {% endif %}
              {% if p.has_package %}
                · <a href=\"/checkout/{{p.product_id}}\" target=\"_blank\">Checkout (Pay with MetaMask)</a>
              {% endif %}
            </td>
            <td>
              {% if p.deployment_url %}
                <a href=\"{{p.deployment_url}}\" target=\"_blank\">Live</a>
              {% else %}
                N/A
              {% endif %}
            </td>
            <td>
              {% if p.status == 'WAITING_FOR_DEPLOYMENT' %}
                <a href=\"/action/publish/{{p.product_id}}\"><button type=\"button\" style=\"background:#f59e0b; color:white; border:none;\">Redeploy</button></a>
              {% else %}
                <a href=\"/action/publish/{{p.product_id}}\"><button type=\"button\">Publish</button></a>
              {% endif %}
              <a href=\"/action/test_publish/{{p.product_id}}\"><button type=\"button\">Test Publish</button></a>
              <a href=\"/action/wp_post/{{p.product_id}}\" title="워드프레스에 즉시 포스팅"><button type=\"button\" style=\"background:#21759b; color:white; border:none;\">WP Post</button></a>
              <a href=\"/action/delete_product/{{p.product_id}}\"><button type=\"button\">Delete</button></a>
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
      <div style=\"margin-top:10px; display:flex; gap:8px; align-items:center;\">
        <select name=\"bulk_action\">
          <option value=\"publish\">Publish</option>
          <option value=\"test_publish\">Test Publish</option>
          <option value=\"delete\">Delete</option>
        </select>
        <button type=\"submit\">Apply to selected</button>
        <span class=\"muted\">(여러 개 상품을 한 번에 처리)</span>
      </div>
    </form>
  </div>

  <div class=\"card\" style=\"margin-top:16px\">
    <h2>Orders (data/orders.json)</h2>
    <table>
      <thead>
        <tr><th>order_id</th><th>product_id</th><th>amount</th><th>currency</th><th>status</th><th>actions</th></tr>
      </thead>
      <tbody>
          {% for o in orders %}
          <tr>
            <td><code>{{o.order_id}}</code></td>
            <td>
              <code>{{o.product_id}}</code><br/>
              <small class="muted" style="font-size: 11px;">{{o.product_title}}</small>
            </td>
            <td>{{o.amount}}</td>
            <td>{{o.currency}}</td>
            <td>
              <span class=\"badge badge-{{o.status}}\">{{o.status}}</span>
            </td>
            <td>
              {% if o.status == 'paid' %}
                <a href=\"/api/pay/token?order_id={{o.order_id}}\" target=\"_blank\">Get Download Token</a>
              {% else %}
                <form method=\"post\" action=\"/action/mark_paid\" style=\"display:inline\">
                  <input type=\"hidden\" name=\"order_id\" value=\"{{o.order_id}}\"/>
                  <button type=\"submit\">Mark Paid (test)</button>
                </form>
              {% endif %}
            </td>
          </tr>
          {% endfor %}
      </tbody>
    </table>
  </div>

  <div class=\"grid\" style=\"margin-top:16px\">
    <div class=\"card\">
      <h2>Logs: payment</h2>
      <pre>{{log_payment}}</pre>
    </div>
    <div class=\"card\">
      <h2>Logs: preview</h2>
      <pre>{{log_preview}}</pre>
    </div>
  </div>

  <div class="card">
      <h2>Secrets (키 관리)</h2>
      <div class="muted" style="margin-bottom:10px;">
        {% set essential_keys = ['VERCEL_API_TOKEN', 'NOWPAYMENTS_API_KEY', 'JWT_SECRET_KEY'] %}
        {% for k in essential_keys %}
          <span style="margin-right:8px;">
            {{k}}: {% if secrets.get(k) %}<span style="color:#22c55e">● Set</span>{% else %}<span style="color:#ef4444">○ Missing</span>{% endif %}
          </span>
        {% endfor %}
      </div>
      <form method=\"post\" action=\"/action/save_secrets\">
      <label class=\"muted\">LEMON_SQUEEZY_API_KEY</label>
      <input name=\"LEMON_SQUEEZY_API_KEY\" value=\"{{secrets.get('LEMON_SQUEEZY_API_KEY','')}}\" />
      <label class=\"muted\">GITHUB_TOKEN</label>
      <input name=\"GITHUB_TOKEN\" value=\"{{secrets.get('GITHUB_TOKEN','')}}\" />
      <label class=\"muted\">VERCEL_API_TOKEN</label>
      <input name=\"VERCEL_API_TOKEN\" value=\"{{secrets.get('VERCEL_API_TOKEN','')}}\" />
      <label class=\"muted\">VERCEL_PROJECT_ID</label>
      <input name=\"VERCEL_PROJECT_ID\" value=\"{{secrets.get('VERCEL_PROJECT_ID','')}}\" />
      <label class=\"muted\">VERCEL_ORG_ID</label>
      <input name=\"VERCEL_ORG_ID\" value=\"{{secrets.get('VERCEL_ORG_ID','')}}\" />
      <label class=\"muted\">JWT_SECRET_KEY</label>
      <input name=\"JWT_SECRET_KEY\" value=\"{{secrets.get('JWT_SECRET_KEY','')}}\" />
      <label class=\"muted\">NOWPAYMENTS_API_KEY</label>
      <input name=\"NOWPAYMENTS_API_KEY\" value=\"{{secrets.get('NOWPAYMENTS_API_KEY','')}}\" />
      <label class=\"muted\">PAYMENT_MODE (mock/nowpayments)</label>
      <input name=\"PAYMENT_MODE\" value=\"{{secrets.get('PAYMENT_MODE','mock')}}\" />
      <label class=\"muted\">AI_QUALITY_THRESHOLD</label>
      <input name=\"AI_QUALITY_THRESHOLD\" value=\"{{secrets.get('AI_QUALITY_THRESHOLD','85')}}\" />
      <label class=\"muted\">DOWNLOAD_TOKEN_SECRET (공통 보안 키)</label>
      <input name=\"DOWNLOAD_TOKEN_SECRET\" value=\"{{secrets.get('DOWNLOAD_TOKEN_SECRET','')}}\" placeholder=\"자동 생성됨\" />
      <label class="muted">DOWNLOAD_TOKEN_TTL_SECONDS (토큰 유효 시간)</label>
      <input name="DOWNLOAD_TOKEN_TTL_SECONDS" value="{{secrets.get('DOWNLOAD_TOKEN_TTL_SECONDS','900')}}" />
      
      <label class="muted">VERCEL_TOKEN (Vercel API Token)</label>
      <input name="VERCEL_TOKEN" value="{{secrets.get('VERCEL_TOKEN','')}}" />
      <label class="muted">GITHUB_TOKEN (GitHub Personal Access Token)</label>
      <input name="GITHUB_TOKEN" value="{{secrets.get('GITHUB_TOKEN','')}}" />
      <label class="muted">MEDIUM_TOKEN (Medium Integration Token)</label>
      <input name="MEDIUM_TOKEN" value="{{secrets.get('MEDIUM_TOKEN','')}}" />

      <h3 style="margin-top:20px;">Blogger (Google Blogspot)</h3>
      <div class="muted" style="margin-bottom:10px;">
        <span style="background:#e0f2fe; color:#0369a1; padding:2px 6px; border-radius:4px; font-weight:bold; margin-right:5px;">Step 1</span>
        <a href="https://console.cloud.google.com/apis/credentials" target="_blank" style="color:#2563eb; font-weight:bold; text-decoration:underline;">Click here to open Google Cloud Console (Credentials)</a><br/>
        OAuth 2.0 Client ID를 생성하고, 리프레시 토큰을 발급받아 입력하세요.
      </div>
      <label class="muted">BLOGGER_CLIENT_ID</label>
      <input name="BLOGGER_CLIENT_ID" value="{{secrets.get('BLOGGER_CLIENT_ID','')}}" />
      <label class="muted">BLOGGER_CLIENT_SECRET</label>
      <input name="BLOGGER_CLIENT_SECRET" value="{{secrets.get('BLOGGER_CLIENT_SECRET','')}}" />
      <label class="muted">BLOGGER_REFRESH_TOKEN</label>
      <input name="BLOGGER_REFRESH_TOKEN" value="{{secrets.get('BLOGGER_REFRESH_TOKEN','')}}" />
      <label class="muted">BLOGGER_BLOG_ID (Blog ID found in URL)</label>
      <input name="BLOGGER_BLOG_ID" value="{{secrets.get('BLOGGER_BLOG_ID','')}}" />

      <h3 style="margin-top:20px;">X (Twitter) API Keys</h3>
      <div class="muted" style="margin-bottom:10px;">
        <a href="https://developer.x.com/en/portal/dashboard" target="_blank" style="color:#3b82f6">X Developer Portal</a>에서 App을 생성하고 <b>Read and Write</b> 권한을 부여한 뒤 아래 키들을 입력하세요.
      </div>
      <label class=\"muted\">X_CONSUMER_KEY</label>
      <input name=\"X_CONSUMER_KEY\" value=\"{{secrets.get('X_CONSUMER_KEY','')}}\" />
      <label class=\"muted\">X_CONSUMER_SECRET</label>
      <input name=\"X_CONSUMER_SECRET\" value=\"{{secrets.get('X_CONSUMER_SECRET','')}}\" />
      <label class=\"muted\">X_ACCESS_TOKEN</label>
      <input name=\"X_ACCESS_TOKEN\" value=\"{{secrets.get('X_ACCESS_TOKEN','')}}\" />
      <label class=\"muted\">X_ACCESS_TOKEN_SECRET</label>
      <input name=\"X_ACCESS_TOKEN_SECRET\" value=\"{{secrets.get('X_ACCESS_TOKEN_SECRET','')}}\" />
      <label class=\"muted\">X_BEARER_TOKEN</label>
      <input name=\"X_BEARER_TOKEN\" value=\"{{secrets.get('X_BEARER_TOKEN','')}}\" />
      
      <p><button type=\"submit\">Save Secrets</button></p>
      <div class=\"muted\">저장 후 실행되는 프로세스(auto_pilot 등)에는 자동으로 환경변수가 주입됩니다.</div>
    </form>
  </div>

  <div class=\"card\" style=\"margin-top:16px\">
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <h2>Promotion Channels</h2>
      <a href="/action/test_wp"><button type="button" style="background:#21759b; color:white; border:none;">Test WP Connection</button></a>
    </div>
    <form method=\"post\" action=\"/action/save_promo_config\">
      <h3>Blog (WordPress)</h3>
      <div class="muted" style="margin-bottom:10px;">
        판테온 워드프레스 또는 자체 워드프레스의 REST API 설정을 입력하세요.<br/>
        <b>WordPress Token:</b> <code>사용자명:비밀번호</code> 형식으로 입력해야 합니다. (예: <code>trae:abcd efgh ijkl mnop</code>)
      </div>
      <label class=\"muted\">Mode (none/webhook/wordpress)</label>
      <input name=\"blog_mode\" value=\"{{promo_cfg.get('blog',{}).get('mode','none')}}\" />
      <label class=\"muted\">Blog webhook URL (커스텀 사이트용)</label>
      <input name=\"blog_webhook_url\" value=\"{{promo_cfg.get('blog',{}).get('webhook_url','')}}\" />
      <label class=\"muted\">WordPress API URL (예: https://site.com/wp-json/wp/v2/posts)</label>
      <input name=\"wp_api_url\" value=\"{{promo_cfg.get('blog',{}).get('wp_api_url','')}}\" />
      <label class=\"muted\">WordPress Token (user:application_password)</label>
      <input name=\"wp_token\" value=\"{{promo_cfg.get('blog',{}).get('wp_token','')}}\" />

      <h3>Medium Integration</h3>
      <div class="muted" style="margin-bottom:10px;">
        <span style="background:#e0f2fe; color:#0369a1; padding:2px 6px; border-radius:4px; font-weight:bold; margin-right:5px;">Step 1</span>
        <a href="https://medium.com/me/settings/security-apps" target="_blank" style="color:#2563eb; font-weight:bold; text-decoration:underline;">Click here to get Medium Integration Token</a><br/>
        (Settings -> Security and apps -> Integration tokens)
      </div>
      <label class="muted">Medium Integration Token</label>
      <input name="medium_token" value="{{promo_cfg.get('medium',{}).get('token','')}}" />

      <h3>Tumblr Integration</h3>
      <div class="muted" style="margin-bottom:10px;">
        <span style="background:#e0f2fe; color:#0369a1; padding:2px 6px; border-radius:4px; font-weight:bold; margin-right:5px;">Step 1</span>
        <a href="https://www.tumblr.com/oauth/apps" target="_blank" style="color:#2563eb; font-weight:bold; text-decoration:underline;">Click here to Register Application (Get Consumer Key/Secret)</a><br/>
        Tumblr API 인증 정보를 입력하세요. (OAuth1)
      </div>
      <label class="muted">Tumblr Blog Identifier (e.g., myblog.tumblr.com)</label>
      <input name="tumblr_blog_identifier" value="{{promo_cfg.get('tumblr',{}).get('blog_identifier','')}}" />
      <label class="muted">Consumer Key</label>
      <input name="tumblr_consumer_key" value="{{promo_cfg.get('tumblr',{}).get('consumer_key','')}}" />
      <label class="muted">Consumer Secret</label>
      <input name="tumblr_consumer_secret" value="{{promo_cfg.get('tumblr',{}).get('consumer_secret','')}}" />
      <label class="muted">OAuth Token</label>
      <input name="tumblr_oauth_token" value="{{promo_cfg.get('tumblr',{}).get('oauth_token','')}}" />
      <label class="muted">OAuth Token Secret</label>
      <input name="tumblr_oauth_token_secret" value="{{promo_cfg.get('tumblr',{}).get('oauth_token_secret','')}}" />

      <h3>GitHub Pages (Jekyll Blog)</h3>
      <div class="muted" style="margin-bottom:10px;">
        <span style="background:#e0f2fe; color:#0369a1; padding:2px 6px; border-radius:4px; font-weight:bold; margin-right:5px;">Step 1</span>
        <a href="https://github.com/settings/tokens" target="_blank" style="color:#2563eb; font-weight:bold; text-decoration:underline;">Click here to generate Personal Access Token</a><br/>
        GitHub Pages(Jekyll) 레포지토리에 Git Push로 포스팅합니다.
      </div>
      <label class=\"muted\">Repository URL (HTTPS)</label>
      <input name=\"gh_repo_url\" value=\"{{promo_cfg.get('github_pages',{}).get('repo_url','')}}\" />
      <label class=\"muted\">Personal Access Token (Repo Scope)</label>
      <input name=\"gh_token\" value=\"{{promo_cfg.get('github_pages',{}).get('token','')}}\" />
      <label class=\"muted\">Username</label>
      <input name=\"gh_username\" value=\"{{promo_cfg.get('github_pages',{}).get('username','')}}\" />

      <h3>Monetization (Ad Revenue)</h3>
      <div class="muted" style="margin-bottom:10px;">
        블로그 포스팅에 자동 삽입될 광고 코드(HTML)를 입력하세요. (Google AdSense 등)
      </div>
      <label class=\"muted\">Ad HTML Code</label>
      <textarea name=\"ad_code\" rows=\"4\" style=\"width:100%; background:#2d3748; color:#e2e8f0; border-radius:10px; border:1px solid #667584; padding:8px;\">{{promo_cfg.get('monetization',{}).get('ad_code','')}}</textarea>

      <h3>Social (webhook 기반)</h3>
      <div class="muted" style="margin-bottom:10px;">
        <span style="background:#e0f2fe; color:#0369a1; padding:2px 6px; border-radius:4px; font-weight:bold; margin-right:5px;">Step 1</span>
        <a href="https://developer.twitter.com/en/portal/dashboard" target="_blank" style="color:#2563eb; font-weight:bold; text-decoration:underline;">Click here to create X App & get Webhook URL</a>
      </div>
      <label><input type="checkbox" name="x_enabled" {% if promo_cfg.get('x',{}).get('enabled') %}checked{% endif %}/> Enable X(Twitter)</label>
      <input name="x_webhook_url" placeholder="X webhook URL" value="{{promo_cfg.get('x',{}).get('webhook_url','')}}" />

      <div class="muted" style="margin-bottom:10px;">
        <span style="background:#e0f2fe; color:#0369a1; padding:2px 6px; border-radius:4px; font-weight:bold; margin-right:5px;">Step 1</span>
        <a href="https://developers.pinterest.com/apps/" target="_blank" style="color:#2563eb; font-weight:bold; text-decoration:underline;">Click here to create Pinterest App</a>
      </div>
      <label><input type="checkbox" name="pinterest_enabled" {% if promo_cfg.get('pinterest',{}).get('enabled') %}checked{% endif %}/> Enable Pinterest</label>
      <input name="pinterest_webhook_url" placeholder="Pinterest webhook URL" value="{{promo_cfg.get('pinterest',{}).get('webhook_url','')}}" />

      <div class="muted" style="margin-bottom:10px;">
        <span style="background:#e0f2fe; color:#0369a1; padding:2px 6px; border-radius:4px; font-weight:bold; margin-right:5px;">Step 1</span>
        <a href="https://www.reddit.com/prefs/apps" target="_blank" style="color:#2563eb; font-weight:bold; text-decoration:underline;">Click here to create Reddit App</a>
      </div>
      <label><input type="checkbox" name="reddit_enabled" {% if promo_cfg.get('reddit',{}).get('enabled') %}checked{% endif %}/> Enable Reddit</label>
      <input name="reddit_webhook_url" placeholder="Reddit webhook URL" value="{{promo_cfg.get('reddit',{}).get('webhook_url','')}}" />

      <div class="muted" style="margin-bottom:10px;">
        <span style="background:#e0f2fe; color:#0369a1; padding:2px 6px; border-radius:4px; font-weight:bold; margin-right:5px;">Step 1</span>
        <a href="https://www.linkedin.com/developers/apps" target="_blank" style="color:#2563eb; font-weight:bold; text-decoration:underline;">Click here to create LinkedIn App</a>
      </div>
      <label><input type="checkbox" name="linkedin_enabled" {% if promo_cfg.get('linkedin',{}).get('enabled') %}checked{% endif %}/> Enable LinkedIn</label>
      <input name="linkedin_webhook_url" placeholder="LinkedIn webhook URL" value="{{promo_cfg.get('linkedin',{}).get('webhook_url','')}}" />

      <div class="muted" style="margin-bottom:10px;">
        <span style="background:#e0f2fe; color:#0369a1; padding:2px 6px; border-radius:4px; font-weight:bold; margin-right:5px;">Step 1</span>
        <a href="https://t.me/BotFather" target="_blank" style="color:#2563eb; font-weight:bold; text-decoration:underline;">Click here to open BotFather (Telegram)</a>
      </div>
      <label><input type="checkbox" name="telegram_enabled" {% if promo_cfg.get('telegram',{}).get('enabled') %}checked{% endif %}/> Enable Telegram</label>
      <input name="telegram_webhook_url" placeholder="Telegram webhook URL" value="{{promo_cfg.get('telegram',{}).get('webhook_url','')}}" />

      <div class="muted" style="margin-bottom:10px;">
        <span style="background:#e0f2fe; color:#0369a1; padding:2px 6px; border-radius:4px; font-weight:bold; margin-right:5px;">Step 1</span>
        <a href="https://discord.com/developers/applications" target="_blank" style="color:#2563eb; font-weight:bold; text-decoration:underline;">Click here to create Discord App</a>
      </div>
      <label><input type="checkbox" name="discord_enabled" {% if promo_cfg.get('discord',{}).get('enabled') %}checked{% endif %}/> Enable Discord</label>
      <input name="discord_webhook_url" placeholder="Discord webhook URL" value="{{promo_cfg.get('discord',{}).get('webhook_url','')}}" />

      <h3>Instagram/TikTok/YouTube Shorts</h3>
      <div class="muted" style="margin-bottom:10px;">
        <span style="background:#e0f2fe; color:#0369a1; padding:2px 6px; border-radius:4px; font-weight:bold; margin-right:5px;">Step 1</span>
        <a href="https://developers.facebook.com/apps/" target="_blank" style="color:#2563eb; font-weight:bold; text-decoration:underline;">Click here to create Instagram App</a>
      </div>
      <label><input type="checkbox" name="instagram_enabled" {% if promo_cfg.get('instagram',{}).get('enabled') %}checked{% endif %}/> Enable Instagram</label>
      <input name="instagram_webhook_url" placeholder="Instagram webhook URL" value="{{promo_cfg.get('instagram',{}).get('webhook_url','')}}" />

      <div class="muted" style="margin-bottom:10px;">
        <span style="background:#e0f2fe; color:#0369a1; padding:2px 6px; border-radius:4px; font-weight:bold; margin-right:5px;">Step 1</span>
        <a href="https://developers.tiktok.com/" target="_blank" style="color:#2563eb; font-weight:bold; text-decoration:underline;">Click here to create TikTok App</a>
      </div>
      <label><input type="checkbox" name="tiktok_enabled" {% if promo_cfg.get('tiktok',{}).get('enabled') %}checked{% endif %}/> Enable TikTok</label>
      <input name="tiktok_webhook_url" placeholder="TikTok webhook URL" value="{{promo_cfg.get('tiktok',{}).get('webhook_url','')}}" />

      <div class="muted" style="margin-bottom:10px;">
        <span style="background:#e0f2fe; color:#0369a1; padding:2px 6px; border-radius:4px; font-weight:bold; margin-right:5px;">Step 1</span>
        <a href="https://console.cloud.google.com/apis/dashboard" target="_blank" style="color:#2563eb; font-weight:bold; text-decoration:underline;">Click here to enable YouTube Data API</a>
      </div>
      <label><input type="checkbox" name="youtube_enabled" {% if promo_cfg.get('youtube_shorts',{}).get('enabled') %}checked{% endif %}/> Enable YouTube Shorts</label>
      <input name="youtube_webhook_url" placeholder="YouTube webhook URL" value="{{promo_cfg.get('youtube_shorts',{}).get('webhook_url','')}}" />

      <label><input type=\"checkbox\" name=\"dry_run\" {% if promo_cfg.get('dry_run', True) %}checked{% endif %}/> Dry-run</label>
      <p><button type=\"submit\">Save Promotion Config</button></p>
    </form>
  </div>

  <script>
    async function updateSystemStatus() {
      try {
        const r = await fetch('/api/system/status');
        const data = await r.json();
        
        for (const [name, info] of Object.entries(data)) {
          const el = document.getElementById(`status-${name}`);
          if (!el) continue;
          const dot = el.querySelector('.dot');
          if (info.alive) {
            dot.className = 'dot dot-online';
          } else if (info.running) {
            dot.className = 'dot dot-starting';
          } else {
            dot.className = 'dot dot-offline';
          }
        }
        
        // Autopilot status check (simple PID check)
        const pids = {{pids | tojson}};
        const apEl = document.getElementById('status-autopilot');
        if (apEl) {
          const apDot = apEl.querySelector('.dot');
          apDot.className = pids.autopilot ? 'dot dot-online' : 'dot dot-offline';
        }
      } catch (e) {
        console.error('Status check failed', e);
      }
    }
    setInterval(updateSystemStatus, 3000);
    updateSystemStatus();

    async function updateProgress() {
      try {
        const res = await fetch('/api/system/progress');
        const data = await res.json();
        
        const card = document.getElementById('progress-card');
        if (!card) return;

        const taskEl = document.getElementById('prog-task');
        const pctEl = document.getElementById('prog-percent');
        const barEl = document.getElementById('prog-bar');
        const statusEl = document.getElementById('prog-status');
        const detailsEl = document.getElementById('prog-details');
        const timeEl = document.getElementById('prog-time');
        
        // Show card always if we have valid data, or keep it visible
        // We only hide if explicitly "Idle" AND "Waiting" for long? 
        // For now, just show whatever is in the JSON.
        card.style.display = 'block';

        taskEl.textContent = data.task || 'Idle';
        const pct = data.progress || 0;
        pctEl.textContent = pct + '%';
        barEl.style.width = pct + '%';
        statusEl.textContent = data.status || '';
        detailsEl.textContent = data.details || '';
        
        if (data.updated_at) {
             const d = new Date(data.updated_at * 1000);
             timeEl.textContent = d.toLocaleTimeString();
        }

      } catch (e) {
        console.error('Progress check failed', e);
      }
    }
    setInterval(updateProgress, 2000);
    updateProgress();
  </script>
</body>
</html>
"""


def _get_system_health():
    """시스템 전체 상태 요약 정보 수집"""
    ledger = None
    try:
        from src.ledger_manager import LedgerManager
        ledger = LedgerManager()
    except Exception:
        pass

    stats = {"total": 0, "published": 0, "failed": 0, "waiting": 0, "total_sales": 0, "revenue": 0}
    if ledger:
        products = ledger.get_all_products()
        stats["total"] = len(products)
        logger.info(f"Stats calculation: Total={len(products)}")
        for p in products:
            status = p.get("status", "UNKNOWN")
            # logger.info(f"Product {p.get('id')} status: {status}")
            
            if status == "PUBLISHED":
                stats["published"] += 1
            elif status == "PROMOTED":
                stats["published"] += 1
                # We can also track promoted separately if needed
            elif status in ["PIPELINE_FAILED", "QA2_FAILED", "QA1_FAILED", "PUBLISH_FAILED"]:
                stats["failed"] += 1
            elif status in ["WAITING_FOR_DEPLOYMENT"]:
                stats["waiting"] += 1
        
        logger.info(f"Calculated Stats: {stats}")
        
        # 판매 통계 추가
        from order_store import FileOrderStore
        store = FileOrderStore(DATA_DIR)
        all_orders = store.list_orders()
        for o in all_orders:
            if o.get("status") == "paid":
                stats["total_sales"] += 1
                try:
                    stats["revenue"] += float(o.get("amount", 0))
                except:
                    pass
    
    # Vercel 리셋 정보 (로그 기반)
    vercel_info = "Checking..."
    try:
        log_file = LOGS_DIR / "product_factory.log"
        if log_file.exists():
            content = log_file.read_text(encoding="utf-8", errors="ignore")
            pattern = r"try again in (\d+)\s*(h|m)"
            matches = list(re.finditer(pattern, content))
            if matches:
                last_match = matches[-1]
                vercel_info = f"Limit: {last_match.group(0)}"
            else:
                vercel_info = "No limit detected"
        else:
            vercel_info = "Log missing"
    except Exception:
        vercel_info = "Error checking"

    return {
        "stats": stats,
        "vercel_info": vercel_info,
        "timestamp": _utc_iso()
    }

def _get_channel_status() -> Dict[str, bool]:
    """secrets.json을 기반으로 각 채널 설정 여부를 확인합니다."""
    secrets = _read_json(SECRETS_PATH, {})
    status = {}
    
    # Helper to check nested or flat
    def check(keys, section=None):
        if section and section in secrets:
            if isinstance(secrets[section], dict):
                if all(k in secrets[section] for k in keys):
                    return True
        return all(secrets.get(k) for k in keys)

    status['wordpress'] = check(['api_url', 'username', 'password'], 'wordpress') or \
                          (secrets.get('WP_API_URL') and secrets.get('WP_USER') and secrets.get('WP_PASSWORD'))
    
    status['medium'] = check(['token'], 'medium') or bool(secrets.get('MEDIUM_TOKEN'))
    
    status['tumblr'] = check(['consumer_key', 'consumer_secret', 'oauth_token', 'oauth_token_secret'], 'tumblr') or \
                       (secrets.get('TUMBLR_CONSUMER_KEY') and secrets.get('TUMBLR_CONSUMER_SECRET'))
                       
    status['blogger'] = check(['client_id', 'client_secret'], 'blogger') or \
                        (secrets.get('BLOGGER_CLIENT_ID') and secrets.get('BLOGGER_CLIENT_SECRET'))
                        
    status['github_pages'] = check(['token', 'repo_url'], 'github') or \
                             (secrets.get('GITHUB_TOKEN') and secrets.get('GITHUB_REPO_URL'))
                             
    status['x'] = check(['api_key', 'api_secret', 'access_token', 'access_token_secret'], 'twitter') or \
                  (secrets.get('TWITTER_API_KEY') and secrets.get('TWITTER_ACCESS_TOKEN'))
                  
    status['reddit'] = check(['client_id', 'client_secret', 'username', 'password'], 'reddit') or \
                       (secrets.get('REDDIT_CLIENT_ID') and secrets.get('REDDIT_USERNAME'))
                       
    status['pinterest'] = check(['access_token'], 'pinterest') or bool(secrets.get('PINTEREST_ACCESS_TOKEN'))
    
    status['linkedin'] = check(['access_token'], 'linkedin') or bool(secrets.get('LINKEDIN_ACCESS_TOKEN'))
    
    status['discord'] = check(['webhook_url'], 'discord') or bool(secrets.get('DISCORD_WEBHOOK_URL'))
    
    status['telegram'] = check(['bot_token', 'chat_id'], 'telegram') or \
                         (secrets.get('TELEGRAM_BOT_TOKEN') and secrets.get('TELEGRAM_CHAT_ID'))
                         
    status['youtube_shorts'] = check(['client_id', 'client_secret', 'refresh_token'], 'youtube') or \
                               (secrets.get('YOUTUBE_CLIENT_ID') and secrets.get('YOUTUBE_CLIENT_SECRET') and secrets.get('YOUTUBE_REFRESH_TOKEN'))
                               
    status['instagram'] = secrets.get('INSTAGRAM_ACCESS_TOKEN') or True # Simulation enabled by default
    status['tiktok'] = secrets.get('TIKTOK_ACCESS_TOKEN') or True # Simulation enabled by default

    return status


@app.route("/")
def home():
    """대시보드 메인: 제품 목록, 주문 목록, 서버/파이프라인 제어."""
    pids = _pids()
    all_products = _list_products()[::-1] # 최신순
    
    # Pagination
    try:
        page = int(request.args.get("page", 1))
    except:
        page = 1
    per_page = 10
    total_pages = (len(all_products) + per_page - 1) // per_page
    products = all_products[(page-1)*per_page : page*per_page]
    
    health = _get_system_health()
    orders_raw = _orders_store().list_orders()
    orders = []
    for o in orders_raw[::-1][:200]:
        orders.append({
            "order_id": o.get("order_id"),
            "product_id": o.get("product_id"),
            "amount": o.get("amount"),
            "currency": o.get("currency"),
            "status": o.get("status"),
        })
    log_payment = _tail_log(LOGS_DIR / "payment.log")
    log_preview = _tail_log(LOGS_DIR / "preview.log")
    auto_status = _read_json(AUTO_MODE_STATUS_PATH, {})
    promo_cfg = load_channel_config()
    secrets = _load_secrets()
    audit_report = _read_json(DATA_DIR / "audit_report.json", {})
    perf_report = _read_json(DATA_DIR / "reports" / "latest_performance.json", {})
    channel_status = _get_channel_status()
    
    return render_template_string(
        TEMPLATE,
        root=str(PROJECT_ROOT),
        pids=pids,
        products=products,
        health=health,
        orders=orders,
        log_payment=log_payment,
        log_preview=log_preview,
        auto_status=auto_status,
        promo_cfg=promo_cfg,
        secrets=secrets,
        channel_status=channel_status,
        page=page,
        total_pages=total_pages,
        total_products_count=len(all_products),
        audit_report=audit_report,
        perf_report=perf_report
    )


@app.route("/action/apply_keys")
def action_apply_keys():
    """secrets.json 설정을 시스템에 즉시 반영"""
    try:
        from src.key_manager import apply_keys
        apply_keys(PROJECT_ROOT, write=True, inject=True)
        return redirect(url_for("home"))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/action/refresh_dashboard")
def action_refresh_dashboard():
    """대시보드 데이터 강제 새로고침"""
    return redirect(url_for("home"))

@app.route("/action/run_audit")
def action_run_audit():
    """감사 봇 즉시 실행"""
    try:
        # subprocess로 audit_bot.py 실행 (src 패키지 모드로 실행)
        cmd = [sys.executable, "-m", "src.audit_bot"]
        p = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        if p.returncode == 0:
            flash("Audit completed successfully.", "success")
        else:
            flash(f"Audit failed: {p.stderr}", "error")
    except Exception as e:
        flash(f"Error running audit: {str(e)}", "error")
    return redirect(url_for("home"))

@app.route("/action/run_perf_analysis")
def action_run_perf_analysis():
    """실적 분석 스크립트 즉시 실행"""
    try:
        from src.performance_analyzer import analyze_performance
        report = analyze_performance()
        if "error" not in report:
            flash(f"Performance analysis completed. (Total Paid: {report['summary']['total_paid']})", "success")
        else:
            flash(f"Performance analysis failed: {report['error']}", "error")
    except Exception as e:
        flash(f"Error running performance analysis: {str(e)}", "error")
    return redirect(url_for("home"))

@app.route("/api/pay/token")
def get_download_token():
    """주문 완료 후 다운로드 토큰을 발급받습니다."""
    import requests
    order_id = request.args.get("order_id")
    if not order_id:
        return jsonify({"error": "missing_order_id"}), 400
    
    # 결제 서버(5000)에서 토큰 요청
    token_url = f"http://127.0.0.1:5000/api/pay/token?order_id={order_id}"
    try:
        resp = requests.get(token_url, timeout=5)
        if resp.status_code != 200:
            return (resp.content, resp.status_code, resp.headers.items())
        
        data = resp.json()
        if not data.get("ok"):
            return jsonify(data), 400
            
        # 프록시 다운로드 링크 생성 (포트 8099 사용)
        download_url = f"/api/pay/download?order_id={order_id}&token={data['token']}"
        
        # HTML로 다운로드 버튼 제공
        return f"""
        <html>
        <body style="font-family: sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; background: #f8fafc;">
            <div style="background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);">
                <h2 style="margin-top: 0; color: #1e293b;">Download Ready!</h2>
                <p style="color: #64748b;">Your purchase is confirmed. Click the button below to download your package.</p>
                <a href="{download_url}" style="display: inline-block; background: #22c55e; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold; margin-top: 1rem;">
                    Download Package (ZIP)
                </a>
                <p style="font-size: 0.8rem; color: #94a3b8; margin-top: 1.5rem;">Order ID: {order_id}</p>
            </div>
        </body>
        </html>
        """
    except Exception as e:
        return jsonify({"error": "payment_server_unreachable", "message": str(e)}), 500

@app.route("/api/pay/download")
def proxy_payment_download():
    """브라우저가 5000포트 직접 접근이 어려울 경우 dashboard(8099)를 통해 결제 서버의 다운로드를 프록시합니다."""
    import requests
    order_id = request.args.get("order_id")
    token = request.args.get("token")
    if not order_id or not token:
        return jsonify({"error": "missing_params"}), 400
    
    payment_url = f"http://127.0.0.1:5000/api/pay/download?order_id={order_id}&token={token}"
    try:
        resp = requests.get(payment_url, stream=True, timeout=10)
        if resp.status_code != 200:
            return (resp.content, resp.status_code, resp.headers.items())
        
        # 파일 다운로드 응답을 스트리밍으로 중계
        return Response(
            resp.iter_content(chunk_size=8192),
            content_type=resp.headers.get('Content-Type'),
            headers={
                'Content-Disposition': resp.headers.get('Content-Disposition'),
                'Content-Length': resp.headers.get('Content-Length')
            }
        )
    except Exception as e:
        return jsonify({"error": "proxy_failed", "message": str(e)}), 500


@app.route("/product/<product_id>/")
@app.route("/product/<product_id>/<path:filename>")
def serve_product_preview(product_id: str, filename: str = "index.html"):
    """
    outputs/<product_id> 폴더의 내용을 정적으로 서빙하여
    대시보드에서 바로 프리뷰를 볼 수 있게 합니다.
    """
    product_dir = OUTPUTS_DIR / product_id
    if not product_dir.exists():
        return f"Product {product_id} not found in outputs.", 404
    
    response = send_from_directory(product_dir, filename)
    # 캐시 방지 헤더 추가 (개발 중 변경사항 즉시 반영)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.route("/download/<product_id>")
def download_package(product_id: str):
    """직접 다운로드는 차단하되, QA용 토큰 경로는 200을 돌려준다."""
    if request.path.endswith("/token"):
        return jsonify({"ok": True, "product_id": product_id})
    return (
        jsonify(
            {
                "error": "direct_download_disabled",
                "message": "Use Checkout and pay to get a download link.",
                "checkout_url": f"/checkout/{product_id}",
            }
        ),
        403,
    )


@app.route("/download/startup_bundle")
def download_startup_bundle():
    """START_AUTO 스크립트 묶음을 zip으로 내려받기."""
    root = Path(__file__).resolve().parent
    ps1 = root / "START_AUTO.ps1"
    bat = root / "START_AUTO.bat"
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", compression=zipfile.ZIP_DEFLATED) as z:
        if ps1.exists():
            z.write(ps1, arcname="START_AUTO.ps1")
        if bat.exists():
            z.write(bat, arcname="START_AUTO.bat")
    mem.seek(0)
    return send_file(
        mem,
        as_attachment=True,
        download_name="START_AUTO_bundle.zip",
        mimetype="application/zip",
    )


@app.route("/action/start_payment")
def action_start_payment():
    if _is_windows():
        _kill_port(5000)
    _stop_process("payment")
    # Using python -u for unbuffered output to avoid blocking
    resp = _start_process("payment", [sys.executable, "-u", "backend/payment_server.py"])
    time.sleep(1.5)
    return redirect(url_for("home"))


@app.route("/action/stop_payment")
def action_stop_payment():
    _stop_process("payment")
    if _is_windows():
        _kill_port(5000)
    return redirect(url_for("home"))


@app.route("/action/start_preview")
def action_start_preview():
    if _is_windows():
        _kill_port(8090)
    _stop_process("preview")
    resp = _start_process("preview", [sys.executable, "-u", "preview_server.py"])
    time.sleep(1.5)
    return redirect(url_for("home"))


@app.route("/action/stop_preview")
def action_stop_preview():
    _stop_process("preview")
    if _is_windows():
        _kill_port(8090)
    return redirect(url_for("home"))


@app.route("/action/stop_autopilot")
def action_stop_autopilot():
    _stop_process("autopilot")
    return redirect(url_for("home"))


@app.route("/action/test_wp")
def action_test_wp():
    """워드프레스 연결 테스트"""
    from promotion_dispatcher import _publish_wordpress, load_channel_config
    cfg = load_channel_config()
    blog_cfg = cfg.get("blog", {})
    wp_api_url = blog_cfg.get("wp_api_url")
    wp_token = blog_cfg.get("wp_token")
    
    if not wp_api_url or not wp_token:
        flash("워드프레스 설정(API URL, Token)이 누락되었습니다.", "error")
        return redirect(url_for("home"))
    
    ok, msg = _publish_wordpress(
        wp_api_url, 
        wp_token, 
        "Dashboard Connection Test", 
        "<p>This is a test post from dashboard.</p>"
    )
    if ok:
        flash(f"워드프레스 연결 성공! (상태: {msg})", "success")
    else:
        flash(f"워드프레스 연결 실패: {msg}. 'user:password' 형식을 확인하세요.", "error")
    return redirect(url_for("home"))


@app.route("/action/wp_post/<product_id>")
def action_wp_post(product_id):
    """특정 상품을 워드프레스에 포스팅"""
    from promotion_dispatcher import _publish_wordpress, load_channel_config, build_channel_payloads
    cfg = load_channel_config()
    blog_cfg = cfg.get("blog", {})
    wp_api_url = blog_cfg.get("wp_api_url")
    wp_token = blog_cfg.get("wp_token")
    
    if not wp_api_url or not wp_token:
        flash("워드프레스 설정이 누락되었습니다.", "error")
        return redirect(url_for("home"))
        
    try:
        payloads = build_channel_payloads(product_id)
        title = payloads.get("title") or product_id
        html = payloads.get("blog", {}).get("html", "")
        
        ok, msg = _publish_wordpress(wp_api_url, wp_token, title, html)
        if ok:
            # WordPress Post ID 추출 및 저장
            import re
            match = re.search(r"post_id=(\d+)", str(msg))
            if match:
                wp_post_id = match.group(1)
                from src.ledger_manager import LedgerManager
                lm = LedgerManager()
                prod = lm.get_product(product_id)
                if prod:
                    meta = prod.get("metadata") or {}
                    meta["wp_post_id"] = wp_post_id
                    lm.create_product(product_id, topic=prod.get("topic"), metadata=meta)
                    print(f"WordPress Post ID {wp_post_id} saved for {product_id} via action_wp_post")
            flash(f"상품 {product_id} 워드프레스 포스팅 성공!", "success")
        else:
            flash(f"포스팅 실패: {msg}", "error")
    except Exception as e:
        flash(f"오류 발생: {e}", "error")
        
    return redirect(url_for("home"))


@app.route("/action/save_promo_config", methods=["POST"])
def save_promo_config_action():
    """
    대시보드 폼에서 채널 설정 저장.
    tokens/urls 등 민감정보는 로컬 data/promo_channels.json에만 저장한다.
    """
    cfg = load_channel_config()

    # blog
    blog_mode = (request.form.get("blog_mode") or "none").strip().lower()
    blog_webhook_url = (request.form.get("blog_webhook_url") or "").strip()
    wp_api_url = (request.form.get("wp_api_url") or "").strip()
    wp_token = (request.form.get("wp_token") or "").strip()

    cfg["blog"] = {
        "mode": blog_mode,
        "webhook_url": blog_webhook_url,
        "wp_api_url": wp_api_url,
        "wp_token": wp_token,
    }

    # Tumblr
    cfg["tumblr"] = {
        "blog_identifier": (request.form.get("tumblr_blog_identifier") or "").strip(),
        "consumer_key": (request.form.get("tumblr_consumer_key") or "").strip(),
        "consumer_secret": (request.form.get("tumblr_consumer_secret") or "").strip(),
        "oauth_token": (request.form.get("tumblr_oauth_token") or "").strip(),
        "oauth_token_secret": (request.form.get("tumblr_oauth_token_secret") or "").strip(),
    }

    # GitHub Pages
    cfg["github_pages"] = {
        "repo_url": (request.form.get("gh_repo_url") or "").strip(),
        "token": (request.form.get("gh_token") or "").strip(),
        "username": (request.form.get("gh_username") or "").strip(),
    }

    # Blogger
    cfg["blogger"] = {
        "client_id": (request.form.get("blogger_client_id") or "").strip(),
        "client_secret": (request.form.get("blogger_client_secret") or "").strip(),
        "refresh_token": (request.form.get("blogger_refresh_token") or "").strip(),
        "blog_id": (request.form.get("blogger_blog_id") or "").strip(),
    }

    # Monetization
    cfg["monetization"] = {
        "ad_code": (request.form.get("ad_code") or "").strip(),
    }

    # instagram / tiktok / youtube_shorts + 추가 채널
    def _b(name: str) -> bool:
        return (request.form.get(name) or "").strip() in ["1", "true", "on", "yes"]

    cfg["x"] = {
        "enabled": _b("x_enabled"),
        "webhook_url": (request.form.get("x_webhook_url") or "").strip(),
    }
    cfg["pinterest"] = {
        "enabled": _b("pinterest_enabled"),
        "webhook_url": (request.form.get("pinterest_webhook_url") or "").strip(),
    }
    cfg["reddit"] = {
        "enabled": _b("reddit_enabled"),
        "webhook_url": (request.form.get("reddit_webhook_url") or "").strip(),
    }
    cfg["linkedin"] = {
        "enabled": _b("linkedin_enabled"),
        "webhook_url": (request.form.get("linkedin_webhook_url") or "").strip(),
    }
    cfg["telegram"] = {
        "enabled": _b("telegram_enabled"),
        "webhook_url": (request.form.get("telegram_webhook_url") or "").strip(),
    }
    cfg["discord"] = {
        "enabled": _b("discord_enabled"),
        "webhook_url": (request.form.get("discord_webhook_url") or "").strip(),
    }
    cfg["instagram"] = {
        "enabled": _b("instagram_enabled"),
        "webhook_url": (request.form.get("instagram_webhook_url") or "").strip(),
    }
    cfg["tiktok"] = {
        "enabled": _b("tiktok_enabled"),
        "webhook_url": (request.form.get("tiktok_webhook_url") or "").strip(),
    }
    cfg["youtube_shorts"] = {
        "enabled": _b("youtube_enabled"),
        "webhook_url": (request.form.get("youtube_webhook_url") or "").strip(),
    }

    # safety
    cfg["dry_run"] = _b("dry_run")

    save_channel_config(cfg)
    return redirect(url_for("home"))

@app.route("/action/save_secrets", methods=["POST"])
def save_secrets_action():
    data = _load_secrets() # 기존 값 유지하면서 업데이트
    for key in [
        "LEMON_SQUEEZY_API_KEY",
        "GITHUB_TOKEN",
        "VERCEL_TOKEN",
        "VERCEL_API_TOKEN",
        "VERCEL_PROJECT_ID",
        "VERCEL_ORG_ID",
        "JWT_SECRET_KEY",
        "NOWPAYMENTS_API_KEY",
        "PAYMENT_MODE",
        "AI_QUALITY_THRESHOLD",
        "DOWNLOAD_TOKEN_SECRET",
        "DOWNLOAD_TOKEN_TTL_SECONDS",
        "MEDIUM_TOKEN",
    ]:
        val = (request.form.get(key) or "").strip()
        if val:
            data[key] = val
    
    # secrets.json에 먼저 저장
    _save_secrets(data)
    
    # key_manager를 통해 통합 저장 및 .env 동기화
    apply_keys(PROJECT_ROOT, write=True, inject=True)
    
    return redirect(url_for("home"))


@app.route("/action/test_publish/<product_id>")
def test_publish(product_id: str):
    """
    현재 채널 설정으로 '발행'을 한 번 실행(가능하면 webhook/wordpress로 전송).
    키가 없으면 파일만 생성되고 no-op.
    """
    try:
        product_dir = OUTPUTS_DIR / product_id
        if not product_dir.exists():
            return jsonify({"ok": False, "error": "product_not_found"}), 404

        # ready 표시 + 채널 디스패치
        mark_ready_to_publish(product_dir=product_dir, product_id=product_id)
        res = dispatch_publish(product_id)
        return jsonify({"ok": True, "result": res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/action/start_auto_mode", methods=["POST"])
def action_start_auto_mode():
    interval = int(request.form.get("interval", "3600") or "3600")
    batch = int(request.form.get("auto_batch", "1") or "1")
    topic = str(request.form.get("auto_topic", "")).strip()
    deploy = (
        1
        if str(request.form.get("auto_deploy", "0")).strip()
        in ("1", "true", "on", "yes")
        else 0
    )
    publish = (
        1
        if str(request.form.get("auto_publish", "1")).strip()
        in ("1", "true", "on", "yes")
        else 0
    )

    cmd = [
        sys.executable,
        "auto_mode_daemon.py",
        "--interval",
        str(interval),
        "--batch",
        str(batch),
        "--deploy",
        str(deploy),
        "--publish",
        str(publish),
    ]
    if topic:
        cmd += ["--topic", topic]
    _start_process("auto_mode", cmd)
    return redirect(url_for("home"))


@app.route("/action/stop_auto_mode")
def action_stop_auto_mode():
    _stop_process("auto_mode")
    return redirect(url_for("home"))


@app.route("/action/run_autopilot", methods=["POST"])
def action_run_autopilot():
    batch = int(request.form.get("batch", "1") or "1")
    topic = str(request.form.get("topic", "")).strip()
    seed = int(time.time())

    cmd = [sys.executable, "auto_pilot.py", "--batch", str(batch), "--seed", str(seed)]
    if topic:
        cmd += ["--topic", topic]

    # 대시보드는 "실행만" 하고, 로그는 파일로 남김
    _start_process("autopilot", cmd)
    return redirect(url_for("home"))


@app.route("/action/rebuild_product", methods=["POST"])
def action_rebuild_product():
    product_id = str(request.form.get("product_id", "")).strip()
    topic = str(request.form.get("topic", "")).strip()
    if not product_id or not topic:
        return jsonify({"error": "product_id_and_topic_required"}), 400

    # 기존 폴더 삭제 후 재생성
    d = OUTPUTS_DIR / product_id
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)

    meta = generate_one(
        ProductConfig(outputs_dir=OUTPUTS_DIR, topic=topic, product_id=product_id)
    )
    return redirect(url_for("home"))


@app.route("/action/delete_product/<product_id>")
def action_delete_product(product_id: str):
    # 1. WordPress 포스트 삭제 시도 (사용자 요청으로 비활성화: 삭제된 상품 홍보글은 남김)
    """
    try:
        from src.ledger_manager import LedgerManager
        from promotion_dispatcher import _delete_wordpress_post, load_channel_config
        lm = LedgerManager()
        prod = lm.get_product(product_id)
        if prod and prod.get("metadata"):
            meta = prod.get("metadata")
            wp_post_id = meta.get("wp_post_id")
            if wp_post_id:
                cfg = load_channel_config()
                blog_cfg = cfg.get("blog", {})
                wp_api_url = blog_cfg.get("wp_api_url")
                wp_token = blog_cfg.get("wp_token")
                if wp_api_url and wp_token:
                    ok, msg = _delete_wordpress_post(wp_api_url, wp_token, wp_post_id)
                    print(f"WordPress post {wp_post_id} deletion for {product_id}: {ok}, {msg}")
    except Exception as e:
        print(f"WordPress deletion failed for {product_id}: {e}")
    """

    # 2. 로컬 디렉토리 삭제
    d = OUTPUTS_DIR / product_id
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    
    # 3. 원장 레코드도 삭제
    try:
        from src.ledger_manager import LedgerManager
        lm = LedgerManager()
        lm.delete_product_record(product_id)
    except Exception:
        pass
        
    return redirect(url_for("home"))


@app.route("/action/bulk_products", methods=["POST"])
def action_bulk_products():
    ids = request.form.getlist("product_id")
    action = (request.form.get("bulk_action") or "").strip()
    if not ids or action not in {"publish", "test_publish", "delete"}:
        return redirect(url_for("home"))

    for pid in ids:
        try:
            if action == "publish":
                d = OUTPUTS_DIR / pid
                if d.exists():
                    from src.ledger_manager import LedgerManager
                    from src.publisher import Publisher
                    lm = LedgerManager()
                    
                    # 0. Ensure status is PACKAGED so publisher can proceed
                    prod = lm.get_product(pid)
                    if not prod:
                        lm.create_product(pid, topic="unknown_bulk", metadata={})
                    lm.update_product_status(pid, status="PACKAGED")

                    mark_ready_to_publish(product_dir=d, product_id=pid)
                    # 1. Dispatch promotions (webhooks etc)
                    try:
                        dispatch_publish(pid)
                    except Exception as e:
                        print(f"Promotion dispatch failed for {pid}: {e}")
                    
                    # 2. Vercel deployment (if possible)
                    try:
                        pub = Publisher(lm)
                        pub.publish_product(pid, str(d))
                    except Exception as e:
                        print(f"Vercel deployment skipped or failed for {pid}: {e}")
            elif action == "test_publish":
                d = OUTPUTS_DIR / pid
                if d.exists():
                    mark_ready_to_publish(product_dir=d, product_id=pid)
                    dispatch_publish(pid)
            elif action == "delete":
                # WordPress 포스트 삭제 시도 (사용자 요청으로 비활성화: 삭제된 상품 홍보글은 남김)
                """
                try:
                    from src.ledger_manager import LedgerManager
                    from promotion_dispatcher import _delete_wordpress_post, load_channel_config
                    lm = LedgerManager()
                    prod = lm.get_product(pid)
                    if prod and prod.get("metadata"):
                        meta = prod.get("metadata")
                        wp_post_id = meta.get("wp_post_id")
                        if wp_post_id:
                            cfg = load_channel_config()
                            blog_cfg = cfg.get("blog", {})
                            wp_api_url = blog_cfg.get("wp_api_url")
                            wp_token = blog_cfg.get("wp_token")
                            if wp_api_url and wp_token:
                                _delete_wordpress_post(wp_api_url, wp_token, wp_post_id)
                except:
                    pass
                """

                d = OUTPUTS_DIR / pid
                if d.exists():
                    shutil.rmtree(d, ignore_errors=True)
                    # 원장 레코드도 삭제 시도
                    try:
                        from src.ledger_manager import LedgerManager
                        lm = LedgerManager()
                        lm.delete_product_record(pid)
                    except Exception:
                        pass
        except Exception as e:
            print(f"bulk action failed ({action}, {pid}): {e}")
    return redirect(url_for("home"))


@app.route("/action/run_recovery")
def action_run_recovery():
    """복구 스크립트 실행"""
    _start_process("recovery", [sys.executable, "failed_product_recovery.py"])
    return redirect("/")

@app.route("/action/redeploy_waiting")
def action_redeploy_waiting():
    """WAITING_FOR_DEPLOYMENT 상태인 제품들만 골라서 재배포 시도"""
    _start_process("redeploy", [sys.executable, "redeploy_waiting.py"])
    return redirect("/")

@app.route("/action/check_vercel")
def action_check_vercel():
    """Vercel 리셋 상태 확인 스크립트 실행"""
    _start_process("vercel_check", [sys.executable, "check_vercel_reset.py"])
    return redirect("/")

@app.route("/action/vercel_cleanup")
def action_vercel_cleanup():
    """Vercel 프로젝트 정리 (오래된 프로젝트 삭제)"""
    from src.ledger_manager import LedgerManager
    from src.publisher import Publisher
    lm = LedgerManager()
    pub = Publisher(lm)
    try:
        # 비동기로 실행하지 않고 대시보드에서 즉시 실행 (개수가 많지 않으면 금방 끝남)
        # Git Push 모드에서는 일반적으로 불필요하나 수동 실행 시에는 190개 제한으로 실행
        pub.cleanup_old_projects(max_projects=190)
        flash("Vercel 프로젝트 정리가 완료되었습니다. (Git Push 모드에서는 일반적으로 불필요합니다)", "success")
    except Exception as e:
        flash(f"Vercel 프로젝트 정리 실패: {str(e)}", "error")
    return redirect("/")

@app.route("/action/publish/<product_id>")
def action_publish(product_id: str):
    d = OUTPUTS_DIR / product_id
    if not d.exists():
        return jsonify({"error": "product_not_found", "product_id": product_id}), 404
    
    from src.ledger_manager import LedgerManager
    from src.publisher import Publisher
    lm = LedgerManager()

    # Ensure status is PACKAGED so publisher can proceed
    prod = lm.get_product(product_id)
    if not prod:
        lm.create_product(product_id, topic="unknown_single", metadata={})
    lm.update_product_status(product_id, status="PACKAGED")

    mark_ready_to_publish(product_dir=d, product_id=product_id)
    
    # 1. Dispatch promotions
    try:
        res = dispatch_publish(product_id)
        # WordPress Post ID 추출 및 저장
        sent_items = res.get("sent", [])
        wp_post_id = None
        for item in sent_items:
            if item.get("channel") == "blog_wordpress" and "post_id=" in str(item.get("msg")):
                import re
                match = re.search(r"post_id=(\d+)", str(item.get("msg")))
                if match:
                    wp_post_id = match.group(1)
                    break
        
        if wp_post_id:
            prod = lm.get_product(product_id)
            if prod:
                meta = prod.get("metadata") or {}
                meta["wp_post_id"] = wp_post_id
                lm.create_product(product_id, topic=prod.get("topic"), metadata=meta)
                print(f"WordPress Post ID {wp_post_id} saved for {product_id}")
                
    except Exception as e:
        print(f"Promotion dispatch failed for {product_id}: {e}")

    # 2. Vercel deployment
    try:
        pub = Publisher(lm)
        pub.publish_product(product_id, str(d))
    except Exception as e:
        print(f"Vercel deployment skipped or failed for {product_id}: {e}")

    return redirect(url_for("home"))


@app.route("/action/mark_paid", methods=["POST"])
def action_mark_paid():
    order_id = str(request.form.get("order_id", "")).strip()
    if not order_id:
        return jsonify({"error": "order_id_required"}), 400
    mark_paid_testonly(order_id=order_id, project_root=PROJECT_ROOT)
    return redirect(url_for("home"))


# -----------------------------
# MetaMask(EVM) 결제: 체크아웃 페이지 및 API
# -----------------------------

_CHECKOUT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Checkout — {{ product_id }}</title>
  <style>
    :root { --bg:#0f172a; --card:#1e293b; --text:#e2e8f0; --muted:#94a3b8; --accent:#3b82f6; }
    body { font-family: system-ui, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 24px; min-height: 100vh; }
    .container { max-width: 480px; margin: 0 auto; }
    .card { background: var(--card); border-radius: 12px; padding: 24px; margin-bottom: 16px; border: 1px solid rgba(255,255,255,0.08); }
    h1 { font-size: 1.25rem; margin: 0 0 8px 0; }
    .muted { color: var(--muted); font-size: 0.875rem; }
    .row { display: flex; justify-content: space-between; margin: 12px 0; }
    .price { font-size: 1.5rem; font-weight: 700; color: var(--accent); }
    button { width: 100%; padding: 14px; border-radius: 10px; border: none; font-size: 1rem; cursor: pointer; font-weight: 600; }
    .btn-primary { background: var(--accent); color: #fff; }
    .btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
    input { width: 100%; padding: 12px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.2); background: rgba(0,0,0,0.3); color: var(--text); box-sizing: border-box; margin-top: 8px; }
    .success { background: rgba(34,197,94,0.2); border: 1px solid rgba(34,197,94,0.5); padding: 12px; border-radius: 8px; margin-top: 12px; }
    .success a { color: #4ade80; }
    .error { color: #f87171; font-size: 0.875rem; margin-top: 8px; }
    #txHashForm { margin-top: 16px; }
    label { display: block; margin-top: 12px; color: var(--muted); }
  </style>
</head>
<body>
  <div class="container">
    <div class="card">
      <h1>{{ product_id }}</h1>
      <p class="muted">Digital product — pay with MetaMask (EVM)</p>
      <div class="row">
        <span class="muted">Price</span>
        <span class="price" id="priceDisplay">—</span>
      </div>
      <div class="row">
        <span class="muted">Network</span>
        <span id="chainDisplay">Chain ID {{ chain_id }}</span>
      </div>
      <div class="row">
        <span class="muted">Pay to</span>
        <span class="muted" style="font-size: 0.75rem; word-break: break-all;" id="merchantAddr">{{ merchant_wallet_address }}</span>
      </div>

      <button type="button" class="btn-primary" id="btnPay" onclick="payWithMetaMask()">Pay with MetaMask</button>
      <p class="error" id="err"></p>

      <div id="txHashForm" style="display:none;">
        <label class="muted">If you already sent the transaction, paste TX hash and verify:</label>
        <input type="text" id="txHashInput" placeholder="0x..."/>
        <button type="button" class="btn-primary" style="margin-top:8px;" onclick="verifyTx()">Verify payment</button>
      </div>

      <div id="successBox" class="success" style="display:none;">
        Payment verified. <a id="downloadLink" href="">Download your file</a>
      </div>
    </div>
  </div>
  <script>
    const productId = {{ product_id | tojson }};
    const chainId = {{ chain_id }};
    const tokenSymbol = {{ token_symbol | tojson }};
    const priceWei = {{ price_wei }};
    const merchantAddress = {{ merchant_wallet_address | tojson }};
    const rpcUrl = {{ rpc_url | tojson }};

    function weiToEth(w) {
      const s = (Number(w) / 1e18).toFixed(6);
      return s + ' ' + tokenSymbol;
    }
    document.getElementById('priceDisplay').textContent = weiToEth(priceWei);

    let currentOrderId = null;

    async function payWithMetaMask() {
      const errEl = document.getElementById('err');
      const btn = document.getElementById('btnPay');
      
      // Create or reuse status element
      let statusEl = document.getElementById('statusMsg');
      if (!statusEl) {
         statusEl = document.createElement('div');
         statusEl.id = 'statusMsg';
         statusEl.style.marginTop = '10px';
         statusEl.style.color = '#88cc88'; // Light green
         statusEl.style.fontSize = '0.9rem';
         btn.parentNode.insertBefore(statusEl, btn.nextSibling);
      }

      errEl.textContent = '';
      statusEl.textContent = 'Initializing...';
      btn.disabled = true;

      try {
        if (typeof window.ethereum === 'undefined') {
          throw new Error('MetaMask is not installed. Please install it to proceed.');
        }

        statusEl.textContent = 'Requesting accounts...';
        const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
        const from = accounts[0];
        if (!from) throw new Error('No account selected.');

        statusEl.textContent = 'Creating order...';
        const createResp = await fetch('/api/payment/create_order', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ product_id: productId, buyer_wallet: from })
        });
        
        if (!createResp.ok) {
            throw new Error(`Order creation failed: ${createResp.statusText}`);
        }
        
        const createData = await createResp.json();
        if (createData.error) {
          throw new Error(createData.error);
        }
        
        currentOrderId = createData.order_id;
        const expectedWei = createData.expected_amount_wei;
        const hexValue = '0x' + BigInt(expectedWei).toString(16);
        const hexChainId = '0x' + Number(chainId).toString(16);

        statusEl.textContent = `Switching to Chain ID ${chainId}...`;
        
        try {
            await window.ethereum.request({
                method: 'wallet_switchEthereumChain',
                params: [{ chainId: hexChainId }]
            });
        } catch (switchError) {
            console.warn('Switch chain failed:', switchError);
            
            // This error code indicates that the chain has not been added to MetaMask.
            if (switchError.code === 4902) {
                if (rpcUrl) {
                    statusEl.textContent = 'Adding chain to MetaMask...';
                    try {
                        await window.ethereum.request({
                            method: 'wallet_addEthereumChain',
                            params: [{
                                chainId: hexChainId,
                                chainName: `Chain ${chainId}`, // Generic name if unknown
                                rpcUrls: [rpcUrl],
                                nativeCurrency: {
                                    name: tokenSymbol,
                                    symbol: tokenSymbol,
                                    decimals: 18
                                }
                            }]
                        });
                        // Retry switch? Usually addChain switches automatically or asks user to switch.
                    } catch (addError) {
                         throw new Error(`Failed to add chain: ${addError.message}`);
                    }
                } else {
                     throw new Error(`Chain ID ${chainId} not found in MetaMask and no RPC URL configured.`);
                }
            } else if (switchError.code === 4001) {
                throw new Error('User rejected network switch.');
            } else {
                // Try to proceed anyway? Maybe user is already on correct chain but switch failed for other reason?
                // Or maybe just throw.
                console.error(switchError);
                // We will try to proceed, but likely tx will fail if chain is wrong.
            }
        }

        statusEl.textContent = 'Requesting payment signature...';
        const txHash = await window.ethereum.request({
          method: 'eth_sendTransaction',
          params: [{ to: merchantAddress, from: from, value: hexValue }] // Removed data: '0x' to be safer
        });
        
        statusEl.textContent = 'Verifying payment...';
        if (txHash) {
          await verifyWithTxHash(txHash, from);
        }
      } catch (e) {
        console.error(e);
        errEl.textContent = e.message || String(e);
        statusEl.textContent = '';
        if (e.message && !e.message.includes('User rejected')) {
            document.getElementById('txHashForm').style.display = 'block';
        }
      } finally {
        btn.disabled = false;
      }
    }

    async function verifyTx() {
      const txHash = document.getElementById('txHashInput').value.trim();
      if (!txHash) return;
      const accounts = await window.ethereum?.request({ method: 'eth_requestAccounts' }).catch(() => []);
      await verifyWithTxHash(txHash, accounts[0] || null);
    }

    async function verifyWithTxHash(txHash, buyerWallet) {
      const errEl = document.getElementById('err');
      const body = { tx_hash: txHash, chain_id: chainId, product_id: productId, buyer_wallet: buyerWallet || '' };
      if (currentOrderId) body.order_id = currentOrderId;
      
      try {
          const resp = await fetch('/api/payment/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
          });
          const data = await resp.json();
          if (data.ok && data.download_url) {
            document.getElementById('err').textContent = '';
            document.getElementById('statusMsg').textContent = 'Payment confirmed!';
            document.getElementById('successBox').style.display = 'block';
            const link = document.getElementById('downloadLink');
            link.href = data.download_url;
            link.textContent = 'Download your file';
            document.getElementById('txHashForm').style.display = 'none';
            document.getElementById('btnPay').style.display = 'none';
          } else {
            errEl.textContent = data.error || 'Verification failed';
          }
      } catch (e) {
          errEl.textContent = 'Verification request failed: ' + e.message;
      }
    }
  </script>
</body>
</html>
"""


def _checkout_config(product_id: str):
    """체크아웃용 상품/체인 설정. 패키지 없으면 None."""
    pkg = OUTPUTS_DIR / product_id / "package.zip"
    if not pkg.exists():
        return None
    cfg = get_evm_config(PROJECT_ROOT)
    price_wei = get_product_price_wei(PROJECT_ROOT, product_id)
    return {
        "product_id": product_id,
        "price_wei": price_wei,
        "merchant_wallet_address": cfg.get("merchant_wallet_address"),
        "chain_id": cfg.get("chain_id"),
        "token_symbol": cfg.get("token_symbol", "ETH"),
        "rpc_url": cfg.get("rpc_url"),
    }


@app.route("/checkout/<product_id>")
def checkout_page(product_id: str):
    """체크아웃 페이지: 상품 정보 + MetaMask 결제 UI."""
    cfg = _checkout_config(product_id)
    if not cfg or not cfg.get("merchant_wallet_address"):
        return jsonify({"error": "product_not_available_or_merchant_not_configured"}), 404
    return render_template_string(_CHECKOUT_HTML, **cfg)


@app.route("/api/payment/create_order", methods=["POST"])
def api_payment_create_order():
    """EVM 주문 생성. body: {product_id, buyer_wallet?}."""
    data = request.get_json(silent=True) or request.form or {}
    product_id = str(data.get("product_id") or "").strip()
    buyer_wallet = (data.get("buyer_wallet") or "").strip() or None
    if not product_id:
        return jsonify({"error": "product_id_required"}), 400
    result = create_order_evm(PROJECT_ROOT, product_id=product_id, buyer_wallet=buyer_wallet)
    if result.get("error"):
        return jsonify(result), 400
    return jsonify(result)


@app.route("/api/payment/verify", methods=["POST"])
def api_payment_verify():
    """온체인 결제 검증. body: {tx_hash, chain_id, product_id, buyer_wallet?, order_id?}."""
    data = request.get_json(silent=True) or request.form or {}
    tx_hash = str(data.get("tx_hash") or "").strip()
    chain_id = data.get("chain_id")
    product_id = str(data.get("product_id") or "").strip()
    buyer_wallet = (data.get("buyer_wallet") or "").strip() or None
    order_id = (data.get("order_id") or "").strip() or None
    if not tx_hash or chain_id is None:
        return jsonify({"ok": False, "error": "tx_hash_and_chain_id_required"}), 400
    result = verify_evm_payment(
        PROJECT_ROOT,
        tx_hash=tx_hash,
        chain_id=int(chain_id),
        product_id=product_id,
        buyer_wallet=buyer_wallet,
        order_id=order_id,
    )
    if not result.get("ok"):
        return jsonify(result), 400
    return jsonify(result)


@app.route("/download_token/<token>")
def download_token_route(token: str):
    """토큰 검증 후 패키지 zip 제공. 결제 검증된 경우에만 토큰 발급되므로 게이팅 완료."""
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    user_agent = request.headers.get("User-Agent", "")
    result = validate_download_token_and_consume(
        PROJECT_ROOT,
        token=token,
        log_download=True,
        ip=ip,
        user_agent=user_agent,
    )
    if not result.get("ok"):
        return jsonify({"error": result.get("error"), "detail": result}), 403
    from flask import send_file as sf
    return sf(
        result["package_path"],
        as_attachment=True,
        download_name=result.get("filename", "package.zip"),
        mimetype="application/zip",
    )


def _auto_start_servers_if_enabled() -> None:
    """
    무인 운영 편의:
    - 기본값: payment/preview 서버를 자동 기동한다.
    - 끄려면: AUTO_START_SERVERS=0 환경변수 설정
    """
    flag = os.getenv("AUTO_START_SERVERS", "1").strip()
    if flag in ("0", "false", "False", "no", "NO"):
        return

    # 이미 PID가 있으면 건드리지 않는다(중복 실행 방지)
    p = _pids()

    if "payment" not in p:
        cmd = [sys.executable, "backend/payment_server.py"]
        _start_process("payment", cmd)

    if "preview" not in p:
        cmd = [sys.executable, "preview_server.py"]
        _start_process("preview", cmd)


@app.route("/ultimate", methods=["GET"])
def ultimate_page():
    # 초보자용 단일 페이지(간단)
    return """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8"/>
  <title>MetaPassiveIncome ULTIMATE Dashboard</title>
  <style>
    body{font-family:Arial, sans-serif; margin:20px;}
    .box{border:1px solid #ddd; padding:12px; margin-bottom:12px; border-radius:8px;}
    button{padding:8px 12px; margin-right:8px;}
    input{padding:6px; width:120px;}
    pre{background:#f7f7f7; padding:10px; border-radius:8px; overflow:auto;}
  </style>
</head>
<body>
<h2>ULTIMATE 대시보드</h2>

<div class="box">
  <h3>1) 제품 생성 (auto_pilot)</h3>
  <div>
    batch: <input id="batch" value="1"/>
    languages: <input id="langs" value="en,ko"/>
    <button onclick="runAuto()">실행</button>
  </div>
  <pre id="runlog"></pre>
</div>

<div class="box">
  <h3>2) 스케줄러</h3>
  interval(min): <input id="interval" value="180"/>
  max/day: <input id="maxday" value="2"/>
  languages: <input id="slangs" value="en,ko"/>
  <button onclick="schedUpdate()">설정저장</button>
  <button onclick="schedStart()">시작</button>
  <button onclick="schedStop()">중지</button>
  <button onclick="schedStatus()">상태</button>
  <pre id="schedlog"></pre>
</div>

<div class="box">
  <h3>3) 포트폴리오</h3>
  <button onclick="portfolio()">리포트 생성/조회</button>
  <pre id="portlog"></pre>
</div>

<script>
async function runAuto(){
  const batch=document.getElementById('batch').value;
  const langs=document.getElementById('langs').value;
  const r=await fetch('/api/dashboard/run_auto', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({batch:batch, languages:langs})});
  document.getElementById('runlog').textContent=await r.text();
}
async function schedUpdate(){
  const interval=document.getElementById('interval').value;
  const maxday=document.getElementById('maxday').value;
  const langs=document.getElementById('slangs').value;
  const r=await fetch('/api/dashboard/scheduler', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({interval_minutes:interval, max_products_per_day:maxday, languages:langs})});
  document.getElementById('schedlog').textContent=await r.text();
}
async function schedStart(){
  const r=await fetch('/api/dashboard/scheduler/start', {method:'POST'});
  document.getElementById('schedlog').textContent=await r.text();
}
async function schedStop(){
  const r=await fetch('/api/dashboard/scheduler/stop', {method:'POST'});
  document.getElementById('schedlog').textContent=await r.text();
}
async function schedStatus(){
  const r=await fetch('/api/dashboard/scheduler', {method:'GET'});
  document.getElementById('schedlog').textContent=await r.text();
}
async function portfolio(){
  const r=await fetch('/api/dashboard/portfolio', {method:'GET'});
  document.getElementById('portlog').textContent=await r.text();
}
</script>
</body>
</html>
# """
# 
# 
# @app.route("/api/dashboard/scheduler", methods=["GET", "POST"])
# def api_scheduler():
#     if request.method == "GET":
#         return jsonify(SCHED.status())
#     data = request.get_json(silent=True) or {}
#     SCHED.update(
#         interval_minutes=int(data.get("interval_minutes") or 180),
#         max_products_per_day=int(data.get("max_products_per_day") or 2),
#         languages=str(data.get("languages") or "en,ko"),
#     )
#     return jsonify({"ok": True, "status": SCHED.status()})
# 
# 
# @app.route("/api/dashboard/scheduler/start", methods=["POST"])
# def api_scheduler_start():
#     SCHED.start()
#     return jsonify({"ok": True, "status": SCHED.status()})
# 
# 
# @app.route("/api/dashboard/scheduler/stop", methods=["POST"])
# def api_scheduler_stop():
#     SCHED.stop()
#     return jsonify({"ok": True, "status": SCHED.status()})
# 
# 
# @app.route("/api/dashboard/portfolio", methods=["GET"])
# def api_portfolio():
#     p = write_portfolio_report(PROJECT_ROOT)
#     return jsonify(
#         {
#             "ok": True,
#             "path": str(p),
#             "items": [it.__dict__ for it in build_portfolio(PROJECT_ROOT)],
#         }
#     )
# 
# 
# @app.route("/api/dashboard/run_auto", methods=["POST"])
# def api_run_auto():
#     import subprocess
# 
#     data = request.get_json(silent=True) or {}
#     batch = str(data.get("batch") or "1")
#     languages = str(data.get("languages") or "en,ko")
#     cmd = ["python", "auto_pilot.py", "--batch", batch, "--languages", languages]
#     proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
#     return jsonify(
#         {
#             "ok": True,
#             "returncode": proc.returncode,
#             "stdout": proc.stdout[-4000:],
#             "stderr": proc.stderr[-4000:],
#         }
#     )
# 
# 
# ===============================
# Serve generated product pages
# URL:
#   /product/<product_id>/index.html
#   /product/<product_id>   (auto -> index.html)
# ===============================
# 
# OUTPUTS_DIR = Path(__file__).resolve().parent / "outputs"
# 
# 

@app.route("/product/<product_id>/<path:filename>")
def serve_product_assets(product_id, filename):
    """상품 폴더 내의 기타 에셋(이미지 등) 서빙"""
    product_dir = OUTPUTS_DIR / product_id
    return send_from_directory(str(product_dir), filename)

@app.route("/product/<path:product_path>")
def serve_product_page_fallback(product_path):
    full_path = OUTPUTS_DIR / product_path
    if full_path.is_dir():
        # 폴더명이면 index.html 시도
        index_file = full_path / "index.html"
        if index_file.exists():
            return send_from_directory(str(full_path), "index.html")
    
    # 파일명이면 직접 서빙
    if full_path.exists() and full_path.is_file():
        return send_from_directory(str(full_path.parent), full_path.name)
        
    # 둘 다 아니면 404
    abort(404)

@app.route("/<path:maybe_product>")
def legacy_preview_alias(maybe_product):
    blocked_prefixes = (
        "product/",
        "static/",
        "action/",
        "api/",
        "health",
        "favicon.ico",
        "download/",
        "checkout/",
        "download_token/"
    )
    for p in blocked_prefixes:
        if maybe_product == p.rstrip("/") or maybe_product.startswith(p):
            return abort(404)
            
    candidate_dir = OUTPUTS_DIR / maybe_product
    candidate_index = candidate_dir / "index.html"
    if candidate_index.exists() and candidate_index.is_file():
        return send_from_directory(str(candidate_index.parent), candidate_index.name)
        
    candidate_file = OUTPUTS_DIR / maybe_product
    if candidate_file.exists() and candidate_file.is_file():
        return send_from_directory(str(candidate_file.parent), candidate_file.name)
        
    abort(404)

# 
# ===============================
# Deliverables download endpoint
# ===============================
# 
# DELIVERABLES_DIR = Path(__file__).resolve().parent / "deliverables"
# print(">>> DELIVERABLES_DIR =", DELIVERABLES_DIR)
# 
# 
# @app.route("/download/<path:filename>")
# def download_deliverable(filename):
#     """
#     deliverables 폴더의 파일을 직접 다운로드 제공.
#     예: /download/Crypto-Payment-Landing-Page-Template-for-Digital-Products.zip
#     """
#     file_path = DELIVERABLES_DIR / filename
#     if not file_path.exists() or not file_path.is_file():
#         return "Deliverable not found", 404
#     return send_from_directory(
#         str(file_path.parent), file_path.name, as_attachment=True
#     )


if __name__ == "__main__":
    port = DEFAULT_DASHBOARD_PORT
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    _auto_start_servers_if_enabled()
    
    # Auto-start Blog Promotion Bot
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        print("[Bot] Auto-starting Blog Promotion Bot...")
        bot_instance.start()

    app.run(host="127.0.0.1", port=port, debug=True, use_reloader=True)
# ===============================
