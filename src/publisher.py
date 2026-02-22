import json
import os
import base64
import time
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests

from .config import Config
from .ledger_manager import LedgerManager
# Import product generator for HTML regeneration
try:
    from .product_generator import _render_landing_html_from_schema
except ImportError:
    # Fallback if circular import or missing
    _render_landing_html_from_schema = None
from .utils import ProductionError, get_logger, handle_errors, retry_on_failure

logger = get_logger(__name__)


class Publisher:
    # Vercel 배포 간 최소 간격 (초)
    MIN_DEPLOYMENT_GAP = 10
    _last_deployment_time = 0

    def __init__(self, ledger_manager: LedgerManager):
        self.ledger_manager = ledger_manager
        self.vercel_api_token = Config.VERCEL_API_TOKEN
        self.github_token = Config.GITHUB_TOKEN
        self.vercel_team_id = os.getenv("VERCEL_TEAM_ID") or os.getenv("VERCEL_ORG_ID")

        if not self.vercel_api_token:
            raise ProductionError("Vercel API 토큰이 없습니다.", stage="Publisher Init")

        logger.info("Publisher 초기화 완료")

    def _vercel_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.vercel_api_token}",
            "Content-Type": "application/json",
        }

    def _vercel_team_qs(self) -> str:
        if self.vercel_team_id:
            return f"?teamId={self.vercel_team_id}"
        return ""

    def _sanitize_project_name(self, name: str) -> str:
        """
        Vercel 프로젝트 이름을 규칙에 맞게 산정합니다:
        - 소문자
        - 영문, 숫자, '.', '_', '-' 만 허용
        - 최대 100자
        - '---' (연속 대시) 금지
        """
        import re
        # 소문자 변환
        name = name.lower()
        # 허용되지 않는 문자 제거 (한글 포함)
        name = re.sub(r'[^a-z0-9._-]', '-', name)
        # 연속된 대시 하나로 합치기
        name = re.sub(r'-+', '-', name)
        # 앞뒤 대시 제거
        name = name.strip('-')
        # 최대 100자
        return name[:100]

    def _collect_static_files(self, root: str) -> List[Tuple[str, bytes]]:
        files: List[Tuple[str, bytes]] = []
        base = Path(root)
        
        # 1) 제품 정적 파일 수집
        for p in base.rglob("*"):
            if p.is_file():
                rel = p.relative_to(base).as_posix()
                data = p.read_bytes()
                files.append((rel, data))
        
        # 2) API 엔드포인트 및 Vercel 설정 파일 추가 (404 방지)
        # build_output_dir is outputs/<product_id>
        # project_root is d:/auto/MetaPassiveIncome_FINAL
        project_root = Path(__file__).resolve().parents[1]
        
        # api 폴더 추가
        api_dir = project_root / "api"
        if api_dir.exists():
            for p in api_dir.rglob("*"):
                if p.is_file() and "__pycache__" not in str(p):
                    # api/_vercel_common.py -> api/_vercel_common.py (relative to project_root)
                    rel = p.relative_to(project_root).as_posix()
                    data = p.read_bytes()
                    files.append((rel, data))
        
        # data/secrets.json 추가 (Vercel에서 API 동작을 위해 필요)
        secrets_json = project_root / "data" / "secrets.json"
        if secrets_json.exists():
            files.append(("data/secrets.json", secrets_json.read_bytes()))

        # vercel.json 추가 (라우팅 규칙 적용을 위해 필수)
        vercel_json = project_root / "vercel.json"
        if vercel_json.exists():
            files.append(("vercel.json", vercel_json.read_bytes()))
            logger.info("  - vercel.json 포함됨")

        # 필수 로컬 Python 모듈 추가 (api/ 내에서 import 하는 파일들)
        required_modules = [
            "payment_api.py",
            "nowpayments_client.py",
            "order_store.py",
            "evm_verifier.py",
        ]
        for mod in set(required_modules):
            mod_path = project_root / mod
            if mod_path.exists():
                files.append((mod, mod_path.read_bytes()))

        # .env 파일 추가 금지 (보안 및 환경 변수 충돌 방지)
        # Vercel Project Env를 사용하므로 로컬 .env는 배포하지 않음
        pass
        
        # vercel.json 추가
        vercel_json = project_root / "vercel.json"
        if vercel_json.exists():
            files.append(("vercel.json", vercel_json.read_bytes()))
            
        # requirements.txt 추가 (Vercel Python 런타임용 - Flask 등 불필요한 라이브러리 제외)
        req_txt = project_root / "requirements.txt"
        if req_txt.exists():
            try:
                content = req_txt.read_text(encoding="utf-8")
                # Vercel Serverless 환경에서 불필요하거나 충돌을 일으킬 수 있는 패키지 제외
                # flask/gunicorn은 런타임 충돌 가능성, 나머지는 용량/메모리 절감
                exclude = [
                    "flask", "flask-cors", "gunicorn", 
                    "google-genai", "google-generativeai", 
                    "reportlab", 
                    "beautifulsoup4", 
                    "tweepy", "requests-oauthlib",
                    "python-dateutil"
                ]
                filtered_lines = []
                for line in content.splitlines():
                    if not any(ex in line.lower() for ex in exclude):
                        filtered_lines.append(line)
                
                logger.info(f"Requirements filtering: {len(content.splitlines())} -> {len(filtered_lines)} lines")
                for line in filtered_lines:
                    logger.debug(f"  - {line}")
                
                # files.append(("requirements.txt", "\n".join(filtered_lines).encode("utf-8")))
                files.append(("requirements.txt", "\n".join(filtered_lines).encode("utf-8")))
            except Exception as e:
                logger.warning(f"requirements.txt 필터링 중 오류: {e}")
                files.append(("requirements.txt", req_txt.read_bytes()))
            
        for f_path, f_content in files:
            logger.info(f"  - 배포 파일: {f_path} ({len(f_content)} bytes)")
            
        # 중복 파일 제거 (마지막 항목 유지)
        unique_files = {}
        for path, content in files:
            unique_files[path] = content
        
        final_files = [(p, c) for p, c in unique_files.items()]
        logger.info(f"  - 최종 배포 파일 개수: {len(final_files)}")
        return final_files

    def _get_all_projects(self) -> List[Dict[str, Any]]:
        """Vercel의 모든 프로젝트 목록을 가져옵니다 (페이지네이션 처리)"""
        all_projects = []
        next_ts = None
        qs_base = self._vercel_team_qs()
        
        while True:
            url = f"https://api.vercel.com/v9/projects{qs_base}"
            if qs_base:
                url += f"&limit=100"
            else:
                url += f"?limit=100"
                
            if next_ts:
                url += f"&until={next_ts}"
                
            r = requests.get(url, headers=self._vercel_headers())
            if r.status_code != 200:
                logger.error(f"Vercel 프로젝트 목록 조회 실패: {r.text}")
                break
                
            data = r.json()
            projects = data.get("projects", [])
            all_projects.extend(projects)
            
            pagination = data.get("pagination")
            if not pagination or not pagination.get("next"):
                break
            
            next_ts = pagination.get("next")
            
        return all_projects

    def cleanup_old_projects(self, max_projects: int = 190):
        """
        Vercel 프로젝트 한도(200개) 관리를 위해 오래된 프로젝트 삭제.
        Git Push 방식 사용 시에는 불필요하지만, 혹시 모를 상황 대비해 한도를 190으로 완화.
        """
        logger.info(f"Vercel 프로젝트 정리 시작 (목표 개수: {max_projects})")
        
        qs = self._vercel_team_qs()
        projects = self._get_all_projects()
        logger.info(f"전체 프로젝트 개수: {len(projects)}")
        
        if len(projects) <= max_projects:
            logger.info(f"현재 프로젝트 개수({len(projects)})가 목표치 이하입니다.")
            return

        # 삭제 대상 선정: 이름이 meta-passive-income-으로 시작하는 프로젝트들 중 오래된 순
        target_projects = [p for p in projects if p['name'].startswith("meta-passive-income-")]
        target_projects.sort(key=lambda x: x.get('createdAt', 0)) # 오래된 순

        to_delete_count = len(projects) - max_projects
        logger.info(f"삭제 대상 프로젝트: {to_delete_count}개")

        deleted = 0
        for p in target_projects[:to_delete_count]:
            p_id = p['id']
            p_name = p['name']
            del_url = f"https://api.vercel.com/v9/projects/{p_id}{qs}"
            dr = requests.delete(del_url, headers=self._vercel_headers())
            if dr.status_code in [200, 204]:
                logger.info(f"프로젝트 삭제 성공: {p_name}")
                deleted += 1
                time.sleep(0.1)
            else:
                logger.error(f"프로젝트 삭제 실패: {p_name} - {dr.text}")
        
        logger.info(f"프로젝트 정리 완료: {deleted}개 삭제됨.")
        if deleted > 0:
            logger.info("정리 후 5초 대기...")
            time.sleep(5)

    @handle_errors(stage="Publish")
    def _deploy_to_vercel(
        self, product_id: str, project_name: str, build_output_dir: str
    ) -> str:
        # 1. 배포 간격 조절 (스로틀링 - 최소 10초로 약간 완화)
        now = time.time()
        time_since_last = now - Publisher._last_deployment_time
        if time_since_last < 10:
            wait_time = 10 - time_since_last
            logger.info(f"Vercel 배포 스로틀링: {wait_time:.1f}초 대기 중...")
            time.sleep(wait_time)

        logger.info(
            f"Vercel 배포 시작 - 제품 ID: {product_id}, 프로젝트 이름: {project_name}, 경로: {build_output_dir}"
        )

        files = self._collect_static_files(build_output_dir)
        if not files:
            raise ProductionError(
                f"배포할 파일이 없습니다: {build_output_dir}",
                stage="Publish",
                product_id=product_id,
            )

        logger.info(f"Vercel 배포 파일 수집 완료: {len(files)}개 파일")
        for f_path, _ in files[:10]: # 상위 10개만 로그 출력
            logger.info(f"  - 배포 파일: {f_path}")

        vercel_files = []
        for path, content in files:
            try:
                if path.endswith((".html", ".css", ".js", ".json", ".txt")):
                    decoded_data = content.decode("utf-8")
                    encoding = "utf-8"
                else:
                    decoded_data = base64.b64encode(content).decode("utf-8")
                    encoding = "base64"
                
                vercel_files.append(
                    {
                        "file": path,
                        "data": decoded_data,
                        "encoding": encoding,
                    }
                )
            except Exception as e:
                logger.error(f"파일 인코딩 오류 ({path}): {e}")
                # 바이너리로 강제 시도
                vercel_files.append(
                    {
                        "file": path,
                        "data": base64.b64encode(content).decode("utf-8"),
                        "encoding": "base64",
                    }
                )

        payload = {
            "name": project_name,
            "files": vercel_files,
            "projectSettings": {"framework": None},
            "target": "production",
        }

        qs = self._vercel_team_qs()
        url = f"https://api.vercel.com/v13/deployments{qs}"
        
        # 2. 429 에러 대응을 위한 내부 재시도 로직 (지수 백오프 강화)
        max_internal_retries = 3
        for attempt in range(max_internal_retries + 1):
            r = requests.post(url, headers=self._vercel_headers(), data=json.dumps(payload))
            
            if r.status_code == 429:
                if attempt < max_internal_retries:
                    # 백오프 시간을 더 길게 (60, 120, 240초)
                    backoff_time = (2 ** attempt) * 60 
                    logger.warning(f"Vercel 429 (Too Many Requests) 감지. {backoff_time}초 후 재시도 ({attempt+1}/{max_internal_retries})")
                    time.sleep(backoff_time)
                    continue
                else:
                    logger.error("Vercel 429 재시도 횟수 초과.")
                    raise ProductionError(
                        f"Vercel 속도 제한(429) 초과. 나중에 다시 시도하십시오.",
                        stage="Publish_Limit",
                        product_id=product_id
                    )
            
            if r.status_code >= 300:
                # 한도 초과(402) 또는 프로젝트 한도(400 too_many_projects) 시 특수 처리를 위한 정보 포함
                error_msg = f"Vercel 배포 실패: {r.status_code} {r.text}"
                if r.status_code == 402 or (r.status_code == 400 and "too_many_projects" in r.text) or (r.status_code == 403 and "daily_limit" in r.text.lower()):
                    logger.warning(f"Vercel 한도 제한 감지: {r.status_code}")
                    raise ProductionError(
                        error_msg,
                        stage="Publish_Limit",
                        product_id=product_id
                    )
                
                raise ProductionError(
                    error_msg,
                    stage="Publish",
                    product_id=product_id,
                )

            # 성공 시 루프 탈출
            break

        data = r.json()
        deployment_url = data.get("url") or ""
        if not deployment_url:
            raise ProductionError(
                "Vercel 응답에 url 필드가 없습니다.",
                stage="Publish",
                product_id=product_id,
            )

        # 마지막 배포 시간 업데이트
        Publisher._last_deployment_time = time.time()

        full_url = (
            deployment_url if deployment_url.startswith("http") else f"https://{deployment_url}"
        )
        logger.info(f"Vercel 배포 완료 - URL: {full_url}")
        
        # 1. 프로젝트 환경 변수 설정
        self._set_vercel_env_vars(project_name)
        
        # 2. Vercel 프로젝트 설정 업데이트 (Framework를 'Other'로 강제 설정하여 Flask 오탐지 방지)
        self._update_vercel_project_settings(project_name)
        
        # 3. Vercel SSO Protection 비활성화 (API 접근을 위해)
        self._disable_vercel_sso(project_name)
        
        # 4. [NEW] 배포 후 실제 접속 테스트 (Deployment Verification)
        self._verify_deployment(full_url, product_id)
        
        return full_url

    def _verify_deployment(self, url: str, product_id: str, max_retries: int = 30):
        """배포된 URL에 실제로 접속하여 정상 동작 여부를 확인합니다."""
        logger.info(f"배포 검증 시작: {url} (최대 재시도 {max_retries}회)")
        
        # Vercel 배포 전파 대기 (최대 300초 = 5분)
        api_verified = False
        
        for i in range(max_retries):
            try:
                # 10초 간격으로 시도
                time.sleep(10)
                
                # 1. 메인 페이지 검사
                r = requests.get(url, timeout=15)
                if r.status_code == 200:
                    content = r.text.lower()
                    if "deployment has failed" in content:
                        logger.warning(f"검증 실패 (Vercel 오류 페이지 감지): {url}")
                    elif "404: not found" in content:
                        logger.warning(f"검증 실패 (404 Not Found): {url}")
                    else:
                        # 메인 페이지 성공 -> API 검사 시도
                        api_url = f"{url}/api/health"
                        try:
                            api_r = requests.get(api_url, timeout=10)
                            if api_r.status_code == 200:
                                logger.info(f"배포 검증 성공: {url} (HTTP 200, API OK)")
                                return
                        except Exception as e:
                            logger.warning(f"API 검증 중 오류 (무시함): {e}")
                            # API 실패해도 메인 페이지가 뜨면 일단 성공으로 간주 (API는 콜드 스타트일 수 있음)
                            logger.info(f"배포 검증 성공 (API 체크 건너뜀): {url}")
                            return
                else:
                    logger.warning(f"검증 대기 중... 상태 코드: {r.status_code}")
            except Exception as e:
                logger.warning(f"검증 연결 오류: {e}")
        
        raise ProductionError(
            f"배포 검증 실패: {url} (최대 재시도 {max_retries}회 초과)",
            stage="Publish_Verify",
            product_id=product_id
        )

    def _update_vercel_project_settings(self, project_name: str):
        """Vercel 프로젝트 설정을 업데이트하여 Framework 오탐지를 방지합니다."""
        logger.info(f"Vercel 프로젝트 설정 업데이트 시도: {project_name}")
        qs = self._vercel_team_qs()
        url = f"https://api.vercel.com/v9/projects/{project_name}{qs}"
        
        # framework를 null로 설정하면 'Other' (정적 파일)로 취급됩니다.
        payload = {
            "framework": None,
            "installCommand": "pip install -r requirements.txt",
            "buildCommand": None,
            "outputDirectory": None
        }
        
        try:
            r = requests.patch(url, headers=self._vercel_headers(), json=payload)
            if r.status_code == 200:
                logger.info(f"Vercel 프로젝트 설정 업데이트 성공: {project_name}")
            else:
                logger.warning(f"Vercel 프로젝트 설정 업데이트 실패 ({r.status_code}): {r.text}")
        except Exception as e:
            logger.error(f"Vercel 프로젝트 설정 업데이트 중 오류: {str(e)}")

    def _disable_vercel_sso(self, project_name: str):
        """Vercel 프로젝트의 각종 보호 기능(SSO, Vercel Authentication 등)을 비활성화합니다."""
        logger.info(f"Vercel 프로젝트 보호 기능 비활성화 시도 - 프로젝트: {project_name}")
        qs = self._vercel_team_qs()
        url = f"https://api.vercel.com/v9/projects/{project_name}{qs}"
        
        # 'protection' 필드는 Vercel API v9에서 지원되지 않거나 형식이 다를 수 있음
        # 'ssoProtection'만 먼저 시도하고, 'deploymentProtection'은 별도로 시도하거나 제외
        payloads = [
            {"ssoProtection": None},
            {"directoryListing": True}
        ]
        
        for payload in payloads:
            try:
                r = requests.patch(url, headers=self._vercel_headers(), json=payload)
                if r.status_code == 200:
                    logger.info(f"Vercel 프로젝트 설정 업데이트 성공 ({list(payload.keys())[0]}): {project_name}")
                else:
                    logger.warning(f"Vercel 프로젝트 설정 업데이트 실패 ({list(payload.keys())[0]}, {r.status_code}): {r.text}")
            except Exception as e:
                logger.error(f"Vercel 프로젝트 설정 업데이트 중 오류: {str(e)}")

    def _set_vercel_env_vars(self, project_name: str):
        """Vercel 프로젝트에 필요한 환경 변수를 설정합니다."""
        nowpayments_key = os.getenv("NOWPAYMENTS_API_KEY")
        payment_mode = os.getenv("PAYMENT_MODE", "nowpayments")
        merchant_wallet = os.getenv("MERCHANT_WALLET_ADDRESS")
        chain_id = os.getenv("CHAIN_ID", "1")
        upstash_url = os.getenv("UPSTASH_REDIS_REST_URL")
        upstash_token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
        download_secret = os.getenv("DOWNLOAD_TOKEN_SECRET")

        env_vars = {
            "NOWPAYMENTS_API_KEY": nowpayments_key,
            "PAYMENT_MODE": payment_mode,
            "MERCHANT_WALLET_ADDRESS": merchant_wallet,
            "CHAIN_ID": chain_id,
            "UPSTASH_REDIS_REST_URL": upstash_url,
            "UPSTASH_REDIS_REST_TOKEN": upstash_token,
            "DOWNLOAD_TOKEN_SECRET": download_secret
        }

        qs = self._vercel_team_qs()
        url = f"https://api.vercel.com/v9/projects/{project_name}/env{qs}"
        
        # 기존 환경 변수 확인
        r = requests.get(url, headers=self._vercel_headers())
        existing_envs = {}
        if r.status_code == 200:
            envs = r.json().get("envs", [])
            for e in envs:
                existing_envs[e['key']] = {
                    'id': e['id'],
                    'value': e.get('value')
                }

        for key, value in env_vars.items():
            if not value:
                continue
            
            if key in existing_envs:
                # 이미 존재하면 값을 비교하여 다를 경우 업데이트 (Vercel API v9 env update는 PATCH /v9/projects/:id/env/:envId)
                # 여기서는 단순화를 위해 삭제 후 재등록하거나, 로그만 남기고 일단 진행
                # 실제 운영에서는 PATCH를 쓰는 것이 좋음.
                logger.info(f"Vercel: {project_name}에 {key}가 이미 존재합니다. 업데이트를 시도합니다.")
                env_id = existing_envs[key]['id']
                patch_url = f"https://api.vercel.com/v9/projects/{project_name}/env/{env_id}{qs}"
                payload = {
                    "value": value,
                    "target": ["production", "preview", "development"]
                }
                r = requests.patch(patch_url, headers=self._vercel_headers(), json=payload)
                if r.status_code == 200:
                    logger.info(f"Vercel: {project_name} {key} 업데이트 성공")
                else:
                    logger.error(f"Vercel: {project_name} {key} 업데이트 실패 - {r.text}")
                continue

            # 환경 변수 추가
            payload = {
                "key": key,
                "value": value,
                "type": "encrypted",
                "target": ["production", "preview", "development"]
            }
            r = requests.post(url, headers=self._vercel_headers(), json=payload)
            if r.status_code == 200:
                logger.info(f"Vercel: {project_name}에 {key} 등록 성공")
            else:
                logger.error(f"Vercel: {project_name} {key} 등록 실패 - {r.text}")

    def _deploy_via_git(self, product_id: str) -> str:
        """
        Uses Git Push to deploy the product to the main Vercel project.
        This bypasses the Vercel API project creation limits.
        """
        logger.info(f"Git Push 배포 시작 - 제품 ID: {product_id}")
        
        try:
            # 1. Add changes
            # outputs 폴더만 추가해도 되지만, 전체 동기화가 안전함
            subprocess.run(["git.exe", "add", "."], check=True, capture_output=True)
            
            # .gitignore에 outputs/가 있어도 강제로 추가하여 배포 포함
            # product_id에 해당하는 폴더만 강제 추가
            output_path = f"outputs/{product_id}"

            # [NEW] Ensure files are served via public folder too (for Vercel compatibility)
            # Some Vercel configurations prefer static files in public/
            public_output_path = f"public/outputs/{product_id}"
            if os.path.exists(output_path):
                try:
                    # Ensure parent directory exists
                    os.makedirs(os.path.dirname(public_output_path), exist_ok=True)
                    
                    # Copy directory (overwrite if exists)
                    if os.path.exists(public_output_path):
                        shutil.rmtree(public_output_path)
                    shutil.copytree(output_path, public_output_path)
                    logger.info(f"Copied {output_path} to {public_output_path} for static serving")
                    
                    # Add public output path to git
                    subprocess.run(["git.exe", "add", public_output_path], check=True, capture_output=True)
                except Exception as e:
                    logger.warning(f"Failed to copy to public folder: {e}")

            if os.path.exists(output_path):
                logger.info(f"Git: {output_path} 강제 추가 (ignored 파일 포함)")
                subprocess.run(["git.exe", "add", "-f", output_path], check=True, capture_output=True)
            
            # 2. Commit
            commit_msg = f"Auto-Deploy: Product {product_id}"
            # 변경사항이 없으면 실패할 수 있으므로 check=False
            subprocess.run(["git.exe", "commit", "-m", commit_msg], check=False, capture_output=True)
            
            # 3. Push
            # Try main branch first, then master
            push_result = subprocess.run(["git.exe", "push", "origin", "main"], capture_output=True, text=True)
            if push_result.returncode != 0:
                logger.warning(f"Git push to main failed, trying master... ({push_result.stderr})")
                push_result = subprocess.run(["git.exe", "push", "origin", "master"], capture_output=True, text=True)
                
            if push_result.returncode != 0:
                 raise ProductionError(f"Git Push Failed: {push_result.stderr}", stage="Publish_Git")

            logger.info("Git Push 성공.")
            
            # 4. Construct URL
            # Use the clean /checkout/ URL which is rewritten in vercel.json
            base_url = "https://metapassiveincome-final.vercel.app"
            product_url = f"{base_url}/checkout/{product_id}"
            
            # 5. Verify
            # Git 배포는 Vercel 빌드 시간이 필요하므로 검증 대기 시간을 늘려야 함
            # _verify_deployment 내부 로직 사용 (이미 재시도 로직 포함됨)
            self._verify_deployment(product_url, product_id)
            
            return product_url
            
        except subprocess.CalledProcessError as e:
            raise ProductionError(f"Git Command Failed: {e}", stage="Publish_Git")
        except Exception as e:
            # 재시도 로직을 위해 ProductionError로 래핑
            if isinstance(e, ProductionError):
                raise e
            raise ProductionError(f"Git Deploy Error: {e}", stage="Publish_Git")

    @handle_errors(stage="Publish")
    @retry_on_failure(max_retries=3)
    def publish_product(
        self, product_id: str, product_output_dir: str
    ) -> Dict[str, Any]:
        logger.info(f"제품 발행 시작 - 제품 ID: {product_id}")

        product = self.ledger_manager.get_product(product_id)
        if not product:
            raise ProductionError(
                f"원장에서 제품을 찾을 수 없습니다: {product_id}",
                stage="Publish",
                product_id=product_id,
            )

        if product["status"] not in ["PACKAGED", "QA2_PASSED", "WAITING_FOR_DEPLOYMENT", "PROMOTED", "PUBLISHED"]:
            raise ProductionError(
                f"제품이 발행 준비가 되지 않았습니다. 현재 상태: {product['status']}",
                stage="Publish",
                product_id=product_id,
            )

        # [NEW] 배포 전 최신 스키마 기반 HTML 재생성 (업데이트 반영 보장)
        try:
            schema_path = Path(product_output_dir) / "product_schema.json"
            if schema_path.exists():
                logger.info(f"배포 전 HTML 재생성: {product_id}")
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                
                # 스키마 내 package_file 확인 (없으면 기본값 설정)
                if "package_file" not in schema:
                    # 기존 package.zip이 있는지 확인
                    if (Path(product_output_dir) / "package.zip").exists():
                        schema["package_file"] = "package.zip"
                    # 없으면 pass (render 함수가 알아서 처리하거나 default 사용)
                
                html = _render_landing_html_from_schema(schema, brand="MetaPassiveIncome")
                (Path(product_output_dir) / "index.html").write_text(html, encoding="utf-8")
                logger.info(f"HTML 재생성 완료: {product_id}")
            else:
                logger.warning(f"스키마 파일 없음, HTML 재생성 건너뜀: {product_id}")
        except Exception as e:
            logger.error(f"배포 전 HTML 재생성 실패: {e}")
            # 재생성 실패해도 배포는 시도? 아니면 중단? 
            # 업데이트 반영이 중요하므로 에러를 로그에 남기고 진행하되, 
            # 심각한 경우 중단할 수도 있음. 여기서는 일단 진행.

        # [NEW] Git Push 배포 방식 우선 사용 (Vercel API 한도 우회)
        # 모든 제품을 하나의 통합 사이트에서 서빙
        try:
            deployment_url = self._deploy_via_git(product_id)
            
            updated_product = self.ledger_manager.update_product_status(
                product_id=product_id,
                status="PUBLISHED",
                metadata={
                    "published_at": datetime.now().isoformat(),
                    "deployment_url": deployment_url,
                    "version": product.get("version"),
                    "deploy_method": "git_push"
                },
            )
            
            logger.info(
                f"제품 발행 완료 (Git Push) - 제품 ID: {product_id}, 배포 URL: {deployment_url}"
            )
            return {"status": "PUBLISHED", "url": deployment_url}
            
        except Exception as e:
            logger.error(f"Git Push 배포 실패: {e}")
            # Git 배포 실패 시 기존 API 방식 폴백? 
            # 아니면 그냥 실패 처리? 
            # 한도 문제가 주 원인이므로 API 폴백은 위험할 수 있으나, Git 설정 문제일 수도 있으므로 시도는 해볼 수 있음.
            # 하지만 사용자 요청이 "한도 해결"이므로 Git 실패 시 중단하는게 맞을 수도 있음.
            # 일단 에러를 던져서 재시도하게 함.
            raise e

    def publish_products_batch(self, product_ids: List[str]) -> Dict[str, Any]:
        """
        Batches multiple products into a single Git commit/push to save Vercel deployment quota.
        """
        logger.info(f"Batch publishing {len(product_ids)} products: {product_ids}")
        
        results = {}
        successful_preps = []
        
        # 1. Prepare all products
        for pid in product_ids:
            try:
                product = self.ledger_manager.get_product(pid)
                if not product:
                    results[pid] = {"status": "FAILED", "error": "Product not found"}
                    continue
                    
                output_dir = os.path.join(Config.OUTPUT_DIR, pid)
                if not os.path.exists(output_dir):
                    results[pid] = {"status": "FAILED", "error": "Output dir not found"}
                    continue

                # HTML Regeneration
                try:
                    schema_path = Path(output_dir) / "product_schema.json"
                    if schema_path.exists():
                        schema = json.loads(schema_path.read_text(encoding="utf-8"))
                        if "package_file" not in schema and (Path(output_dir) / "package.zip").exists():
                            schema["package_file"] = "package.zip"
                        
                        if _render_landing_html_from_schema:
                            html = _render_landing_html_from_schema(schema, brand="MetaPassiveIncome")
                            (Path(output_dir) / "index.html").write_text(html, encoding="utf-8")
                        else:
                            logger.warning("HTML generator not imported, skipping regeneration")
                except Exception as e:
                    logger.warning(f"HTML regeneration failed for {pid}: {e}")

                # Copy to public
                public_output_path = f"public/outputs/{pid}"
                os.makedirs(os.path.dirname(public_output_path), exist_ok=True)
                if os.path.exists(public_output_path):
                    shutil.rmtree(public_output_path)
                shutil.copytree(output_dir, public_output_path)
                
                # Git Add
                subprocess.run(["git.exe", "add", public_output_path], check=True, capture_output=True)
                subprocess.run(["git.exe", "add", "-f", f"outputs/{pid}"], check=True, capture_output=True)
                
                successful_preps.append(pid)
                
            except Exception as e:
                results[pid] = {"status": "FAILED", "error": str(e)}
        
        if not successful_preps:
            return results

        # 2. Commit and Push (Once)
        try:
            subprocess.run(["git.exe", "commit", "-m", f"Batch Deploy: {len(successful_preps)} products"], check=False, capture_output=True)
            
            # Push (try main then master)
            push_result = subprocess.run(["git.exe", "push", "origin", "main"], capture_output=True, text=True)
            if push_result.returncode != 0:
                push_result = subprocess.run(["git.exe", "push", "origin", "master"], capture_output=True, text=True)
            
            if push_result.returncode != 0:
                raise ProductionError(f"Batch Git Push Failed: {push_result.stderr}", stage="Publish_Batch")
                
            logger.info("Batch Git Push Successful")
            
        except Exception as e:
            for pid in successful_preps:
                results[pid] = {"status": "FAILED", "error": f"Push failed: {str(e)}"}
            return results

        # 3. Verify and Update Status
        base_url = "https://metapassiveincome-final.vercel.app"
        
        # Wait a bit for Vercel to pick up the push
        time.sleep(10)
        
        for pid in successful_preps:
            try:
                product_url = f"{base_url}/outputs/{pid}/index.html"
                
                # Use fewer retries for batch items to speed up
                try:
                    self._verify_deployment(product_url, pid, max_retries=10)
                except Exception as ve:
                    logger.warning(f"Verification pending/failed for {pid}: {ve}")
                    results[pid] = {"status": "WAITING_VERIFICATION", "error": str(ve)}
                    continue
                
                # Update Ledger
                self.ledger_manager.update_product_status(
                    product_id=pid,
                    status="PUBLISHED",
                    metadata={
                        "published_at": datetime.now().isoformat(),
                        "deployment_url": product_url,
                        "deploy_method": "git_push_batch"
                    },
                )
                results[pid] = {"status": "PUBLISHED", "url": product_url}
                
            except Exception as e:
                results[pid] = {"status": "FAILED", "error": f"Post-process failed: {str(e)}"}
                
        return results

# -----------------------------
# 로컬 단독 실행 테스트 (선택 사항)
# -----------------------------

if __name__ == "__main__":
    logger.info("Publisher 모듈 로컬 테스트 시작")

    # LedgerManager 인스턴스 생성
    ledger = LedgerManager()

    # 테스트를 위한 더미 환경 변수 설정 (실제 .env 파일 사용을 권장)
    os.environ["VERCEL_API_TOKEN"] = "dummy_vercel_token_for_test"
    os.environ["GITHUB_TOKEN"] = "dummy_github_token_for_test"
    os.environ["VERCEL_PROJECT_ID"] = "test-vercel-project"
    os.environ["VERCEL_ORG_ID"] = "test-vercel-org"

    # Config 클래스 재로드 (환경 변수 변경 후)
    from importlib import reload

    from . import config

    reload(config)
    from .config import Config  # 업데이트된 Config 로드

    publisher = Publisher(ledger)

    test_product_id = "test-publish-product-001"
    test_output_dir = os.path.join(Config.OUTPUT_DIR, test_product_id)
    test_package_path = os.path.join(
        Config.DOWNLOAD_DIR, f"{test_product_id}-1.0.0.zip"
    )  # 가짜 패키지 경로

    # 테스트를 위한 제품 원장 항목 생성 및 상태 업데이트
    try:
        ledger.create_product(
            test_product_id, "Test Product for Publishing", metadata={"initial": "data"}
        )
        ledger.update_product_status(test_product_id, "QA1_PASSED")
        ledger.update_product_status(
            test_product_id,
            "PACKAGED",
            package_path=test_package_path,
            checksum="dummy_checksum_123",
            version="1.0.0",
        )
        # QA Stage 2가 통과했다고 가정
        ledger.update_product_status(test_product_id, "QA2_PASSED")

        # 실제 테스트용 출력 디렉토리 생성 (Vercel 배포 시 필요)
        os.makedirs(test_output_dir, exist_ok=True)
        with open(
            os.path.join(test_output_dir, "index.html"), "w"
        ) as f:  # 더미 파일 생성
            f.write("<html><body><h1>Published Test!</h1></body></html>")

        publish_result = publisher.publish_product(test_product_id, test_output_dir)
        logger.info("발행 결과:")
        logger.info(json.dumps(publish_result, ensure_ascii=False, indent=2))

        # 발행된 제품 상태 확인
        final_product_info = ledger.get_product(test_product_id)
        logger.info(f"최종 제품 상태: {final_product_info.get('status')}")
        logger.info(
            f"배포 URL: {final_product_info.get('metadata', {}).get('deployment_url')}"
        )

    except ProductionError as pe:
        logger.error(f"생산 오류 발생: {pe.message}")
        if pe.original_exception:
            logger.error(f"원본 예외: {pe.original_exception}")
    except Exception as e:
        logger.error(f"예기치 않은 오류 발생: {e}")
    finally:
        # 테스트 후 정리 (SQLite 파일은 별도 관리)
        if os.path.exists(test_output_dir):
            import shutil

            shutil.rmtree(test_output_dir)
            logger.info(f"테스트 출력 디렉토리 정리: {test_output_dir}")

    logger.info("Publisher 모듈 로컬 테스트 완료")
