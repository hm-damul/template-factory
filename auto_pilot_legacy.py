# -*- coding: utf-8 -*-
"""
auto_pilot.py
목적:
- (로컬) 템플릿 생성 → 결제 로직 주입 → 미리보기(Flask)에서 버튼 동작 확인
- (배포) deploy_bundle 생성 → Vercel 배포(선택) → 배포 URL에서도 동일하게 결제/다운로드 동작

이번 수정의 핵심:
1) generator_module 안정화: generate(topic)->html 을 "고정 엔트리"로 사용
2) /api/pay/start, /api/pay/check 405/500 방지:
   - 로컬 Flask(payment_server)에는 CORS preflight(OPTIONS) 지원
   - Vercel serverless(api/)에는 handler에서 OPTIONS/GET/POST 메서드 분기 지원
3) deploy_bundle 구조 안정화 + 중복 API 경로(api/pay/api/pay/...) 생성/복사 금지
   - deploy_bundle/api/pay/start.py, check.py 만 복사
4) report.json 직렬화 안전화:
   - Path, dataclass, 객체 등이 포함돼도 JSON 저장 시 크래시가 나지 않게 _json_safe 적용
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

# generator_module 고정 엔트리: generate(topic)->str
import generator_module  # noqa

# -----------------------------
# 상수/기본값
# -----------------------------

DEFAULT_TOPIC = "Crypto Payment Landing Page Template for Digital Products"
DEFAULT_PRODUCT_ID = "crypto-template-001"

PREVIEW_SERVER_LIST_URL = "http://127.0.0.1:8088/_list"
PAYMENT_SERVER_HEALTH_URL = "http://127.0.0.1:5000/health"


# -----------------------------
# 데이터 구조
# -----------------------------


@dataclass
class DeployBundleInfo:
    bundle_root: str
    index_html: str
    downloads_zip: str


@dataclass
class DeployResult:
    ok: bool
    url: str = ""
    raw: str = ""


# -----------------------------
# 유틸
# -----------------------------


def _now_run_id() -> str:
    """runs 폴더에 쓸 timestamp run_id."""
    return time.strftime("%Y%m%d-%H%M%S")


def _slugify(text: str) -> str:
    text = (text or "").strip().lower()
    out = []
    for ch in text:
        if ch.isalnum():
            out.append(ch)
        else:
            out.append("-")
    s = "".join(out)
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-") or "item"


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _write_text(path: str, text: str) -> None:
    _ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _json_safe(obj):
    """JSON 직렬화 가능한 타입으로 변환(Path/dataclass/기타 객체 방지)."""
    # 1) 기본 JSON 타입은 그대로 반환
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    # 2) Path는 문자열로 변환
    try:
        from pathlib import Path

        if isinstance(obj, Path):
            return str(obj)
    except Exception:
        pass
    # 3) dict는 재귀 변환
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    # 4) list/tuple/set은 list로 재귀 변환
    if isinstance(obj, (list, tuple, set)):
        return [_json_safe(x) for x in obj]
    # 5) dataclass는 dict로 변환 시도
    try:
        import dataclasses

        if dataclasses.is_dataclass(obj):
            return _json_safe(dataclasses.asdict(obj))
    except Exception:
        pass
    # 6) 나머지는 안전하게 문자열로 변환(직렬화 에러 방지)
    try:
        return str(obj)
    except Exception:
        return repr(obj)


def _write_json(path: str, data: Dict) -> None:
    """JSON 저장(순수 JSON 타입만)."""
    _ensure_dir(os.path.dirname(path))
    safe = _json_safe(data)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(safe, f, ensure_ascii=False, indent=2)


def _safe_relpath(path: str) -> str:
    """출력용 상대경로(에러 방지)."""
    try:
        return os.path.relpath(path, os.getcwd())
    except Exception:
        return path


def _run_cmd(cmd: list, cwd: Optional[str] = None) -> Tuple[int, str]:
    """명령 실행 유틸."""
    try:
        cp = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            shell=False,
        )
        out = (cp.stdout or "") + (cp.stderr or "")
        return int(cp.returncode), out
    except Exception as e:
        return 1, f"[run_cmd error] {e}"


def _sha256_file(path: str) -> str:
    """파일 SHA256."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _create_package_zip(product_id: str, html_path: str, out_zip_path: str) -> None:
    """
    다운로드용 package.zip 생성.
    - 최소 구성: index.html + manifest.json
    """
    import zipfile

    manifest = {
        "product_id": product_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "files": ["index.html"],
        "sha256_index_html": _sha256_file(html_path),
    }

    _ensure_dir(os.path.dirname(out_zip_path))
    with zipfile.ZipFile(out_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.write(html_path, arcname="index.html")
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))


# -----------------------------
# deploy_bundle 생성/배포
# -----------------------------


def create_deploy_bundle(
    project_root: str,
    run_dir: str,
    product_id: str,
    final_index_html_path: str,
) -> DeployBundleInfo:
#     """
#     Vercel 배포 단위인 deploy_bundle 폴더 생성.
#     규칙(고정):
#     - deploy_bundle/
#         - index.html
#         - vercel.json
#         - api/pay/start.py
#         - api/pay/check.py
#         - downloads/<product_id>/package.zip
#     """
    bundle_root = os.path.join(run_dir, "deploy_bundle")
    api_pay_dir = os.path.join(bundle_root, "api", "pay")
    downloads_dir = os.path.join(bundle_root, "downloads", product_id)

    _ensure_dir(api_pay_dir)
    _ensure_dir(downloads_dir)

    # 1) index.html 복사
    bundle_index = os.path.join(bundle_root, "index.html")
    shutil.copyfile(final_index_html_path, bundle_index)

    # 2) vercel.json 생성(프로젝트 루트에 없을 수 있으므로 번들에 직접 생성)
    #    - /api/pay/start  -> /api/pay/start.py
    #    - /api/pay/check  -> /api/pay/check.py
    vercel_json_path = os.path.join(bundle_root, "vercel.json")
    vercel_json = {
        "functions": {"api/**/*.py": {"runtime": "python3.12"}},
        "rewrites": [
            {"source": "/api/pay/start", "destination": "/api/pay/start.py"},
            {"source": "/api/pay/check", "destination": "/api/pay/check.py"},
        ],
    }
    _write_json(vercel_json_path, vercel_json)

    # 3) api/pay/start.py, api/pay/check.py 는 "프로젝트 루트의 정식 위치"에서만 복사
    #    - 중복 폴더(api/pay/api/pay/...)는 절대 복사하지 않음
    src_start = os.path.join(project_root, "api", "pay", "start.py")
    src_check = os.path.join(project_root, "api", "pay", "check.py")

    if not os.path.exists(src_start):
        raise FileNotFoundError(f"필수 파일이 없습니다: {src_start}")

    if not os.path.exists(src_check):
        raise FileNotFoundError(f"필수 파일이 없습니다: {src_check}")

    shutil.copyfile(src_start, os.path.join(api_pay_dir, "start.py"))
    shutil.copyfile(src_check, os.path.join(api_pay_dir, "check.py"))

    # 4) downloads/<product_id>/package.zip 생성(프로젝트 루트 outputs의 파일이 아니라, "이번 run 산출물"로 생성)
    out_zip = os.path.join(downloads_dir, "package.zip")
    _create_package_zip(
        product_id=product_id, html_path=bundle_index, out_zip_path=out_zip
    )

    return DeployBundleInfo(
        bundle_root=bundle_root,
        index_html=bundle_index,
        downloads_zip=out_zip,
    )


def deploy_to_vercel(bundle_root: str) -> DeployResult:
    """
    Vercel CLI로 배포.
    - 기본은 배포를 '스킵'할 수 있게 설계되어 있고,
      환경변수 CATP_DEPLOY=1 일 때만 실행하는 식으로 사용 가능.
    """
    if os.getenv("CATP_DEPLOY", "0").strip() != "1":
        return DeployResult(ok=True, url="", raw="[skip] CATP_DEPLOY!=1")

    cmd = ["vercel", "--prod", "--yes"]
    rc, out = _run_cmd(cmd, cwd=bundle_root)

    # output에서 URL 추출(간단 휴리스틱)
    url = ""
    for line in out.splitlines():
        if "https://" in line:
            url = line.strip()
            break

    return DeployResult(ok=(rc == 0), url=url, raw=out)


# -----------------------------
# main
# -----------------------------


def main() -> None:
    # 프로젝트 루트(이 파일 위치 기준)
    project_root = os.path.dirname(os.path.abspath(__file__))

    # 0) 입력값(질문 없이 합리적 기본값 사용)
    #    - 환경변수로 덮어쓸 수 있게 해둠(CURSOR/PS에서 편함)
    topic = os.getenv("CATP_TOPIC", DEFAULT_TOPIC).strip() or DEFAULT_TOPIC
    product_id = (
        os.getenv("CATP_PRODUCT_ID", DEFAULT_PRODUCT_ID).strip() or DEFAULT_PRODUCT_ID
    )

    run_id = _now_run_id()
    created_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
    run_dir = os.path.join(project_root, "runs", f"{run_id}-{_slugify(product_id)}")
    _ensure_dir(run_dir)

    print(f"[auto_pilot] project_root = {_safe_relpath(project_root)}")
    print(f"[auto_pilot] run_dir      = {_safe_relpath(run_dir)}")
    print(f"[auto_pilot] topic        = {topic}")
    print(f"[auto_pilot] product_id    = {product_id}")

    # 1) 생성 (generator_module.generate 고정)
    html = generator_module.generate(topic)

    # 2) outputs/<product_id>/index.html 저장
    out_dir = os.path.join(project_root, "outputs", product_id)
    _ensure_dir(out_dir)
    target_html_path = os.path.join(out_dir, "index.html")
    _write_text(target_html_path, html)

    # 3) 결제 위젯 주입(파일 기반)
    from monetize_module import MonetizeModule, PaymentInjectConfig

    MonetizeModule().inject_payment_logic(
        target_html_path=target_html_path,
        config=PaymentInjectConfig(product_id=product_id, download_file_path=""),
    )

    # 4) deploy_bundle 생성
    bundle_info = create_deploy_bundle(
        project_root=project_root,
        run_dir=run_dir,
        product_id=product_id,
        final_index_html_path=target_html_path,
    )

    # 5) vercel 배포(옵션)
    deploy_result = deploy_to_vercel(bundle_root=bundle_info.bundle_root)

    # 6) report.json 작성(직렬화 안전)
    report = {
        "run_id": run_id,
        "created_at": created_at,
        "product_id": product_id,
        "topic": topic,
        "outputs_index_html": target_html_path,
        "deploy_bundle_root": bundle_info.bundle_root,
        "deploy_bundle_index_html": bundle_info.index_html,
        "deploy_bundle_downloads_zip": bundle_info.downloads_zip,
        "preview_list_url": PREVIEW_SERVER_LIST_URL,
        "payment_health_url": PAYMENT_SERVER_HEALTH_URL,
        "vercel": deploy_result,
        "how_to_local": {
            "preview_server": "python preview_server.py",
            "payment_server": "python backend/payment_server.py",
            "open_preview_list": PREVIEW_SERVER_LIST_URL,
        },
    }
    report_path = os.path.join(out_dir, "report.json")
    _write_json(report_path, report)

    print(f"[OK] report={_safe_relpath(report_path)}")
    if deploy_result.url:
        print(f"[OK] vercel_url={deploy_result.url}")


if __name__ == "__main__":
    main()
