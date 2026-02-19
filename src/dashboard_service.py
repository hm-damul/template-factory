import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template_string,
    request,
    send_file,
    url_for,
)

from .config import Config
from .fulfillment_manager import FulfillmentManager
from .ledger_manager import LedgerManager
from .payment_processor import PaymentProcessor
from .publisher import Publisher
from .utils import (
    ProductionError,
    ensure_parent_dir,
    get_logger,
    handle_errors,
    write_text,
)

# from scheduler_service import SchedulerService # TODO: 스케줄러 서비스 통합
# from portfolio_manager import write_portfolio_report, build_portfolio # TODO: 포트폴리오 관리 통합
# from promotion_factory import mark_ready_to_publish # TODO: 프로모션 팩토리 통합
# from promotion_dispatcher import load_channel_config, save_channel_config, dispatch_publish # TODO: 프로모션 디스패처 통합
# from product_factory import generate_one, ProductConfig # TODO: 기존 product_factory -> product_generator 대체

logger = get_logger(__name__)


class DashboardService:
    """제품 생산 파이프라인의 관리 및 모니터링을 위한 대시보드 서비스"""

    def __init__(self, host="127.0.0.1", port=8099):
        self.app = Flask(__name__)
        self.host = host
        self.port = port

        self.project_root = Path(os.path.dirname(os.path.abspath(__file__))).parent
        self.data_dir = self.project_root / "data"
        self.logs_dir = self.project_root / "logs"
        self.outputs_dir = self.project_root / "outputs"
        self.downloads_dir = self.project_root / "downloads"
        self.pids_path = self.data_dir / "pids.json"
        self.auto_mode_status_path = self.data_dir / "auto_mode_status.json"

        ensure_parent_dir(str(self.data_dir))
        ensure_parent_dir(str(self.logs_dir))
        ensure_parent_dir(str(self.outputs_dir))
        ensure_parent_dir(str(self.downloads_dir))

        self.ledger_manager = LedgerManager(Config.DATABASE_URL)
        self.payment_processor = PaymentProcessor(self.ledger_manager)
        self.publisher = Publisher(self.ledger_manager)
        self.fulfillment_manager = FulfillmentManager(self.ledger_manager)

        self._register_routes()
        logger.info(
            f"DashboardService 초기화 완료. 호스트: {self.host}, 포트: {self.port}"
        )

    def _atomic_write_json(self, path: Path, obj) -> None:
        """JSON 파일을 안전하게 원자적으로 씁니다."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        write_text(str(tmp), json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
        tmp.replace(path)
        logger.debug(f"JSON 파일 원자적 쓰기 완료: {path}")

    def _read_json(self, path: Path, default):
        """JSON 파일을 읽습니다. 파일이 없거나 오류 발생 시 기본값을 반환합니다."""
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"JSON 파일 읽기 실패: {path}, 오류: {e}")
            return default

    def _pids(self) -> Dict[str, Any]:
        """실행 중인 프로세스의 PID 정보를 로드합니다."""
        return self._read_json(self.pids_path, {})

    def _set_pid(self, name: str, pid: int, cmd: List[str], log_file: str) -> None:
        """프로세스 PID 정보를 저장합니다."""
        p = self._pids()
        p[name] = {
            "pid": int(pid),
            "cmd": cmd,
            "log_file": log_file,
            "started_at": self._utc_iso(),
        }
        self._atomic_write_json(self.pids_path, p)
        logger.info(f"PID 설정: {name} -> {pid}")

    def _clear_pid(self, name: str) -> None:
        """프로세스 PID 정보를 삭제합니다."""
        p = self._pids()
        if name in p:
            del p[name]
            self._atomic_write_json(self.pids_path, p)
            logger.info(f"PID 삭제: {name}")

    def _utc_iso(self) -> str:
        """현재 UTC 시간을 ISO 형식으로 반환합니다."""
        return datetime.utcnow().isoformat(timespec="seconds") + "Z"

    def _is_windows(self) -> bool:
        """현재 OS가 Windows인지 확인합니다."""
        return os.name == "nt"

    def _kill_pid(self, pid: int) -> bool:
        """프로세스를 종료합니다(Windows/Unix 대응)."""
        try:
            if self._is_windows():
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True,
                    text=True,
                )
            else:
                os.kill(pid, 15)
            logger.info(f"프로세스 종료 성공: PID {pid}")
            return True
        except Exception as e:
            logger.error(f"프로세스 종료 실패: PID {pid}, 오류: {e}")
            return False

    def _start_process(self, name: str, cmd: List[str]) -> Dict[str, Any]:
        """새로운 프로세스를 백그라운드로 시작합니다."""
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        log_path = self.logs_dir / f"{name}.log"
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                p = subprocess.Popen(
                    cmd,
                    cwd=str(self.project_root),
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    shell=False,
                )
            self._set_pid(name=name, pid=p.pid, cmd=cmd, log_file=str(log_path))
            logger.info(f"프로세스 시작 성공: {name}, PID: {p.pid}")
            return {"ok": True, "pid": p.pid, "log_file": str(log_path)}
        except Exception as e:
            logger.error(f"프로세스 시작 실패: {name}, 오류: {e}")
            return {"ok": False, "error": str(e)}

    def _stop_process(self, name: str) -> Dict[str, Any]:
        """지정된 이름의 프로세스를 종료합니다."""
        info = self._pids().get(name)
        if not info:
            return {"ok": True, "status": "not_running"}
        pid = int(info.get("pid", 0))
        ok = self._kill_pid(pid)
        self._clear_pid(name)
        return {"ok": ok, "pid": pid}

    def _tail_log(self, path: Path, n: int = 200) -> str:
        """로그 파일의 마지막 N줄을 읽어 반환합니다."""
        if not path.exists():
            return "(log not found)"
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            return "\n".join(lines[-max(1, int(n)) :])
        except Exception as e:
            logger.error(f"로그 파일 읽기 실패: {path}, 오류: {e}")
            return "(failed to read log)"

    def _list_products_from_ledger(self) -> List[Dict[str, Any]]:
        """원장에서 제품 목록을 조회합니다."""
        return self.ledger_manager.get_all_products()

    def _list_orders_from_ledger(self) -> List[Dict[str, Any]]:
        """원장에서 주문 목록을 조회합니다."""
        return self.ledger_manager.get_all_orders()

    def _auto_start_servers_if_enabled(self) -> None:
        """
        무인 운영 편의:
        - 기본값: payment/preview 서버를 자동 기동한다.
        - 끄려면: AUTO_START_SERVERS=0 환경변수 설정
        """
        flag = os.getenv("AUTO_START_SERVERS", "1").strip()
        if flag in ("0", "false", "False", "no", "NO"):
            logger.info("AUTO_START_SERVERS가 비활성화되어 서버 자동 시작을 건너뜀.")
            return

        p = self._pids()

        # if "payment" not in p: # TODO: Payment Server를 별도 프로세스로 실행할 경우 활성화
        #     cmd = [sys.executable, str(self.project_root / "backend" / "payment_server.py")]
        #     self._start_process("payment", cmd)

        # if "preview" not in p: # TODO: Preview Server를 별도 프로세스로 실행할 경우 활성화
        #     cmd = [sys.executable, str(self.project_root / "preview_server.py")]
        #     self._start_process("preview", cmd)
        logger.info("서버 자동 시작 로직은 현재 비활성화되어 있습니다.")

    def _render_dashboard_template(self, **context) -> str:
        """대시보드 HTML 템플릿을 렌더링합니다."""
        # 기존 HTML 템플릿을 업데이트하여 새로운 데이터 구조와 플로우를 반영해야 합니다.
        # 특히 제품 목록, 주문 목록, 액션 버튼 등
        # 현재는 간략화된 템플릿을 사용합니다.
        template = """<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\"/>
  <title>MetaPassiveIncome Dashboard</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; background-color: #1a202c; color: #e2e8f0; }
    .grid { display:grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .card { border:1px solid #4a5568; border-radius:12px; padding:14px; background-color: #2d3748; }
    button { padding:8px 12px; border-radius:10px; border:1px solid #667584; background-color: #4a5568; color: #e2e8f0; cursor:pointer; margin-right: 8px; }
    button.primary { background-color: #3f51b5; border-color: #3f51b5; color: white; }
    input { padding:8px; border-radius:10px; border:1px solid #667584; width: 100%; box-sizing: border-box; background-color: #2d3748; color: #e2e8f0; }
    .muted { color:#a0aec0; font-size: 13px; }
    code { background:#4a5568; padding:2px 6px; border-radius:6px; }
    table { width:100%; border-collapse: collapse; margin-top: 10px; }
    th, td { border-bottom:1px solid #4a5568; padding:8px; text-align:left; font-size: 13px; }
    a { color:#63b3ed; }
    pre { white-space: pre-wrap; background:#0b1220; color:#e7eef7; padding:10px; border-radius:10px; max-height:260px; overflow:auto; }
    .status-DRAFT { color: #cbd5e0; }
    .status-QA1_FAILED { color: #e53e3e; }
    .status-QA1_PASSED { color: #ecc94b; }
    .status-PACKAGED { color: #4299e1; }
    .status-QA2_FAILED { color: #e53e3e; }
    .status-QA2_PASSED { color: #68d391; }
    .status-PUBLISHED { color: #38b2ac; }
    .status-PENDING { color: #ecc94b; }
    .status-PAID { color: #68d391; }
    .status-FAILED { color: #e53e3e; }
  </style>
</head>
<body>
  <h1>MetaPassiveIncome Production Dashboard</h1>

  {% if message %}
  <div class="alert-{{message.type}}" style="word-wrap: break-word;">
    {{ message.text | safe }}
  </div>
  {% endif %}
  
  <div class=\"muted\">Project root: <code>{{root}}</code></div>

  <div class=\"grid\">
    <div class=\"card\">
      <h2>Server Controls</h2>
      <div class=\"muted\">대시보드는 Flask 내장 서버로 실행됩니다. 다른 서비스는 직접 관리해야 합니다.</div>
      <p>
        <!-- 기존의 start/stop payment/preview 버튼은 더 이상 필요 없거나, 외부 서비스로 대체됩니다. -->
        <button disabled>Payment Server (External)</button>
        <button disabled>Preview Server (External)</button>
      </p>
      <div class=\"muted\">Running PIDs: {{pids}}</div>
    </div>

    <div class=\"card\">
      <h2>Pipeline Controls</h2>
      <form method=\"post\" action=\"/action/run_autopilot\">
        <label class=\"muted\">제품 주제 (비워두면 자동 생성)</label>
        <input name=\"topic\" value=\"\" placeholder=\"예: Cryptocurrency Wallet Checkout Page\" />
        <p><button type=\"submit\" class=\"primary\">새 제품 생성 시작</button></p>
      </form>

      <form method=\"post\" action=\"/action/rebuild_product\">
        <label class=\"muted\">Product ID로 제품 재생성</label>
        <input name=\"product_id\" value=\"\" placeholder=\"재생성할 제품 ID\" />
        <label class=\"muted\">새로운 주제 (필수)</label>
        <input name=\"topic\" value=\"\" placeholder=\"예: Updated Crypto Dapp Landing\" />
        <p><button type=\"submit\">제품 재생성</button></p>
      </form>
    </div>
  </div>

  <div class=\"card\" style=\"margin-top:16px\">
    <h2>제품 목록</h2>
    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>주제</th>
          <th>상태</th>
          <th>버전</th>
          <th>생성일</th>
          <th>업데이트일</th>
          <th>다운로드 링크</th>
          <th>액션</th>
        </tr>
      </thead>
      <tbody>
        {% for p in products %}
        <tr>
          <td><code>{{p.id}}</code></td>
          <td>{{p.topic}}</td>
          <td><span class=\"status-{{p.status}}\">{{p.status}}</span></td>
          <td>{{p.version or 'N/A'}}</td>
          <td>{{p.created_at}}</td>
          <td>{{p.updated_at}}</td>
          <td>
            {% if p.status == "PUBLISHED" and p.download_url %}
              <a href=\"{{p.download_url}}\" target=\"_blank\">다운로드 (테스트)</a>
            {% else %}
              N/A
            {% endif %}
          </td>
          <td>
            <a href=\"/action/delete_product/{{p.id}}\"><button>삭제</button></a>
            {% if p.status == "QA2_PASSED" %}
                <a href=\"/action/publish_product_action/{{p.id}}\"><button class=\"primary\">게시</button></a>
            {% endif %}
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  <div class=\"card\" style=\"margin-top:16px\">
    <h2>주문 목록</h2>
    <table>
      <thead>
        <tr><th>ID</th><th>제품 ID</th><th>이메일</th><th>금액</th><th>상태</th><th>토큰 사용됨</th><th>액션</th></tr>
      </thead>
      <tbody>
        {% for o in orders %}
        <tr>
          <td><code>{{o.id}}</code></td>
          <td><code>{{o.product_id}}</code></td>
          <td>{{o.customer_email}}</td>
          <td>{{o.amount}} {{o.currency}}</td>
          <td><span class=\"status-{{o.status}}\">{{o.status}}</span></td>
          <td>{{o.token_used}}</td>
          <td>
            {% if o.status == "PENDING" %}
            <form method=\"post\" action=\"/action/mark_order_paid\" style=\"display:inline\">
              <input type=\"hidden\" name=\"order_id\" value=\"{{o.id}}\"/>
              <button type=\"submit\" class=\"primary\">강제 PAID (테스트)</button>
            </form>
            {% elif o.status == "PAID" and not o.token_used %}
            <form method=\"post\" action=\"/action/generate_download_token_action\" style=\"display:inline\">
              <input type=\"hidden\" name=\"order_id\" value=\"{{o.id}}\"/>
              <input type=\"hidden\" name=\"product_id\" value=\"{{o.product_id}}\"/>
              <button type=\"submit\">다운로드 토큰 생성</button>
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
      <h2>로그: payment.log</h2>
      <pre>{{log_payment}}</pre>
    </div>
    <div class=\"card\">
      <h2>로그: product_factory.log</h2>
      <pre>{{log_product_factory}}</pre>
    </div>
  </div>

</body>
</html>
# """
#         return render_template_string(template, **context)
# 
#     def _register_routes(self):
#         """Flask 라우트를 등록합니다."""

        @self.app.route("/health")
        def health():
            return jsonify({"ok": True, "service": "dashboard"})

        @self.app.route("/")
        @handle_errors(stage="Dashboard Load")
        def home():
            pids = self._pids()
            products = self._list_products_from_ledger()
            orders = self._list_orders_from_ledger()

            # 제품별 다운로드 URL 추가 (가상 URL 또는 실제 Vercel URL)
            for p in products:
                # PUBLISHED 상태의 제품에만 다운로드 URL 제공
                if p["status"] == "PUBLISHED":
                    # download_product_with_token 엔드포인트는 토큰을 인자로 받으므로,
                    # 여기서는 토큰 생성 요청을 유도하는 URL을 생성하거나,
                    # 실제 토큰을 미리 생성하여 전달하는 방식 고려
                    # 현재는 더미 토큰을 "생성할 수 있다"는 전제로 링크를 표시
                    # TODO: 실제 토큰 생성 후 URL에 포함하도록 변경
                    p["download_url"] = (
                        f"http://{self.host}:{self.port}/download/{p['id']}/token"
                    )
                else:
                    p["download_url"] = None

            log_payment = self._tail_log(
                self.logs_dir / "payment.log"
            )  # 기존 로그 유지
            log_product_factory = self._tail_log(
                self.logs_dir / "product_factory.log"
            )  # 새로운 통합 로그

            return self._render_dashboard_template(
                root=str(self.project_root),
                pids=pids,
                products=products,
                orders=orders,
                log_payment=log_payment,
                log_product_factory=log_product_factory,
                message=(
                    message if "message" in locals() else None
                ),  # message 인자가 없을 경우 None으로 설정
            )

        @self.app.route("/download/<product_id>/token")
        @handle_errors(stage="Download Request")
        def download_product_with_token(product_id: str):
            """다운로드 토큰을 사용하여 제품 파일을 제공합니다."""
            # 이 엔드포인트는 실제 다운로드 파일이 아니라, 토큰 생성 요청을 받거나
            # 유효한 토큰이 있을 때만 파일 경로를 반환해야 합니다.
            # 실제 파일 다운로드는 FulfillmentManager를 통해 이루어져야 합니다.
            token = request.args.get("token")
            if not token:
                raise ProductionError(
                    "다운로드 토큰이 필요합니다.",
                    stage="Download Request",
                    product_id=product_id,
                )

            # 토큰 유효성 검사 및 다운로드 이행
            fulfillment_result = self.fulfillment_manager.fulfill_download(
                token=token,
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string,
            )

            if fulfillment_result["ok"]:
                file_path = fulfillment_result["download_path"]
                return send_file(
                    file_path,
                    as_attachment=True,
                    download_name=os.path.basename(file_path),
                )
            else:
                return (
                    jsonify(
                        {"error": fulfillment_result.get("error", "다운로드 실패")}
                    ),
                    400,
                )

        @self.app.route("/action/run_autopilot", methods=["POST"])
        @handle_errors(stage="Run Autopilot Action")
        def action_run_autopilot():
            topic = str(request.form.get("topic", "")).strip()
            # TODO: auto_pilot.py를 직접 호출하는 대신, ProductFactory를 통해 파이프라인 시작
            # 임시로 더미 응답
            logger.info(
                f"새 제품 생성 요청 수신 (주제: {topic}). 실제 파이프라인 호출 필요."
            )
            return redirect(url_for("home"))

        @self.app.route("/action/rebuild_product", methods=["POST"])
        @handle_errors(stage="Rebuild Product Action")
        def action_rebuild_product():
            product_id = str(request.form.get("product_id", "")).strip()
            topic = str(request.form.get("topic", "")).strip()
            if not product_id or not topic:
                raise ProductionError(
                    "제품 ID와 주제는 필수입니다.", stage="Rebuild Product Action"
                )

            # 기존 제품 삭제 (원장에서)
            self.ledger_manager.delete_product_record(
                product_id
            )  # TODO: delete_product_record 함수 추가 (현재는 임시 주석)

            from .product_factory import ProductFactory

            factory = ProductFactory(self.project_root)
            factory.create_and_process_product(
                topic, languages=[]
            )  # TODO: 기존 제품의 언어 정보 가져오기
            return redirect(url_for("home"))

        @self.app.route("/action/delete_product/<product_id>")
        @handle_errors(stage="Delete Product Action")
        def action_delete_product(product_id: str):
            # LedgerManager에서 제품 삭제 (데이터베이스 레코드)
            # TODO: LedgerManager에 delete_product_record 메서드 구현 필요
            # 현재는 파일 시스템에서만 삭제
            product_output_dir = self.outputs_dir / product_id
            if product_output_dir.exists():
                shutil.rmtree(product_output_dir, ignore_errors=True)
                logger.info(f"제품 출력 디렉토리 삭제: {product_output_dir}")

            # 패키지 파일도 삭제 (downloads 디렉토리)
            # TODO: product_info에서 package_path를 가져와 삭제해야 함
            # 임시: downloads 디렉토리에서 product_id로 시작하는 zip 파일 삭제
            for f_name in os.listdir(str(self.downloads_dir)):
                if f_name.startswith(product_id) and f_name.endswith(".zip"):
                    os.remove(self.downloads_dir / f_name)
                    logger.info(f"제품 패키지 파일 삭제: {f_name}")

            # LedgerManager에서 제품 삭제 (데이터베이스 레코드)
            self.ledger_manager.delete_product_record(product_id)

            return redirect(url_for("home"))

        @self.app.route("/action/publish_product_action/<product_id>")
        @handle_errors(stage="Publish Product Action")
        def action_publish_product_action(product_id: str):
            product_info = self.ledger_manager.get_product(product_id)
            if not product_info:
                raise ProductionError(
                    f"원장에서 제품을 찾을 수 없습니다: {product_id}",
                    stage="Publish Product Action",
                )

            # TODO: product_output_dir을 올바르게 가져와야 함 (product_info에 저장된 경로 사용)
            product_output_dir = self.outputs_dir / product_id  # 임시 경로

            publish_result = self.publisher.publish_product(
                product_id, str(product_output_dir)
            )
            if publish_result["ok"]:
                logger.info(f"제품 게시 성공: {product_id}")
            else:
                logger.error(
                    f"제품 게시 실패: {product_id}, 오류: {publish_result.get("error", "알 수 없는 오류")}"
                )

            return redirect(url_for("home"))

        @self.app.route("/action/mark_order_paid", methods=["POST"])
        @handle_errors(stage="Mark Order Paid Action")
        def action_mark_order_paid():
            order_id = str(request.form.get("order_id", "")).strip()
            if not order_id:
                raise ProductionError(
                    "주문 ID가 필요합니다.", stage="Mark Order Paid Action"
                )

            order_info = self.ledger_manager.get_order(order_id)
            if not order_info:
                raise ProductionError(
                    f"주문을 찾을 수 없습니다: {order_id}",
                    stage="Mark Order Paid Action",
                )

            dummy_webhook_paid_event = {
                "meta": {
                    "event_name": "order_updated",
                    "custom": {
                        "order_id": order_id,
                        "product_id": order_info["product_id"],
                    },
                },
                "data": {
                    "id": "mock_event",
                    "type": "orders",
                    "attributes": {
                        "status": "paid",
                        "total": order_info["amount"],
                        "currency": order_info["currency"],
                        "first_order_item": {"product_id": "mock_ls_product_id"},
                    },
                },
            }
            self.payment_processor.handle_webhook_event(dummy_webhook_paid_event)
            logger.info(f"주문 강제 PAID 처리 완료: {order_id}")
            return redirect(url_for("home"))

        @self.app.route("/action/generate_download_token_action", methods=["POST"])
        @handle_errors(stage="Generate Download Token Action")
        def action_generate_download_token_action():
            order_id = str(request.form.get("order_id", "")).strip()
            product_id = str(request.form.get("product_id", "")).strip()
            if not order_id or not product_id:
                raise ProductionError(
                    "주문 ID와 제품 ID가 필요합니다.",
                    stage="Generate Download Token Action",
                )

            token_result = self.fulfillment_manager.generate_download_token(
                order_id, product_id
            )
            if token_result["ok"]:
                logger.info(f"다운로드 토큰 생성 성공: {order_id}")
                # 사용자에게 토큰과 다운로드 URL을 직접 보여주는 방식으로 변경
                token = token_result["download_token"]
                expiry = token_result["token_expiry"]
                download_url = f"http://{self.host}:{self.port}/download/{product_id}/token?token={token}"
                return self._render_dashboard_template(
                    root=str(self.project_root),
                    pids=self._pids(),
                    products=self._list_products_from_ledger(),
                    orders=self._list_orders_from_ledger(),
                    log_payment=self._tail_log(self.logs_dir / "payment.log"),
                    log_product_factory=self._tail_log(
                        self.logs_dir / "product_factory.log"
                    ),
                    # 추가 메시지 표시
                    message={
                        "type": "success",
                        "text": f'다운로드 토큰이 생성되었습니다. <br/>토큰: <code>{token}</code> (만료: {expiry})<br/>다운로드 URL: <a href="{download_url}" target="_blank">{download_url}</a>',
                    },
                )
            else:
                logger.error(f"다운로드 토큰 생성 실패: {order_id}")
                return jsonify({"ok": False, "error": "다운로드 토큰 생성 실패"}), 400

    def run(self):
        """Flask 애플리케이션을 실행합니다."""
        self._auto_start_servers_if_enabled()
        logger.info(f"대시보드 서버 시작. http://{self.host}:{self.port}/")
        self.app.run(
            host=self.host, port=self.port, debug=False
        )  # debug=True로 하면 자동 재시작 가능


if __name__ == "__main__":
    # Config 유효성 검사 (애플리케이션 시작 시)
    # Config.validate() # .env 파일이 없으면 여기서 오류 발생

    # 테스트를 위해 임시 환경 변수 설정 (실제 배포 시 .env 사용)
    os.environ["LEMON_SQUEEZY_API_KEY"] = "TEST_LEMON_SQUEEZY_API_KEY_123"
    os.environ["GITHUB_TOKEN"] = "TEST_GITHUB_TOKEN_123"
    os.environ["VERCEL_API_TOKEN"] = "TEST_VERCEL_API_TOKEN_123"
    os.environ["JWT_SECRET_KEY"] = "TEST_JWT_SECRET_KEY_1234567890"
    os.environ["DOWNLOAD_TOKEN_EXPIRY_SECONDS"] = "300"
    os.environ["DATABASE_URL"] = "sqlite:///./test_dashboard.db"
    os.environ["DASHBOARD_PORT"] = "8099"  # 추가

    # Config 클래스 재로드 (환경 변수 변경 후)
    from importlib import reload

    from . import config

    reload(config)
    from .config import Config  # 업데이트된 Config 로드

    dashboard = DashboardService(
        port=Config.DASHBOARD_PORT
    )  # Config.DASHBOARD_PORT 사용
    dashboard.run()
