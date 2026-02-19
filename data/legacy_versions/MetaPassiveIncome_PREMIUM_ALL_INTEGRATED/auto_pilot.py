# -*- coding: utf-8 -*-
"""
auto_pilot.py (production-style single-run orchestrator)

목표:
- 제품 N개를 자동 생성(batch)
- 각 제품에 대해:
  1) 실제 제품 산출물 생성(outputs/<product_id>/...)
  2) 랜딩 페이지 생성(outputs/<product_id>/index.html)
  3) 홍보 패키지 생성(outputs/<product_id>/promotions/*)
  4) 배포 번들 생성(runs/<run_id>/<product_id>/deploy_bundle/)
  5) (선택) Vercel 배포

실행 예시(Windows PowerShell):
  python auto_pilot.py --batch 3
  python auto_pilot.py --batch 1 --topic "Stablecoin Settlement Handbook..."
  python auto_pilot.py --batch 1 --deploy

주의:
- 배포는 vercel CLI가 설치되어 있고, 로그인되어 있어야 한다.
- 본 파일은 "크래시"보다 "완료 가능한 최소 기능"을 우선한다.
"""

from __future__ import annotations

import argparse  # CLI
import json  # report.json 저장
import re  # HTML 치환
import shutil  # 폴더 복사
import subprocess  # vercel CLI
import time  # run_id
from pathlib import Path  # 경로
from typing import Any, Dict, List  # 타입

from dotenv import load_dotenv  # .env

import generator_module  # generate(topic)->html
from product_factory import (
    DEFAULT_TOPICS,
    ProductConfig,
    batch_generate,
    generate_one,
    make_product_id,
)
from promotion_factory import generate_promotions

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
RUNS_DIR = PROJECT_ROOT / "runs"


def _utc_compact() -> str:
    return time.strftime("%Y%m%d-%H%M%S", time.gmtime())


def _atomic_write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


def _run_cmd(cmd: List[str], cwd: Path) -> tuple[int, str]:
    """명령 실행 + 출력 캡처."""
    try:
        p = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True, shell=False
        )
        out = (p.stdout or "") + "\n" + (p.stderr or "")
        return int(p.returncode), out.strip()
    except Exception as e:
        return 1, f"[EXCEPTION] {e}"


def _patch_landing_product_id(html: str, product_id: str) -> str:
    """랜딩 HTML의 productId 변수를 실제 product_id로 치환."""
    # generator_module에서: const productId = "..."; 형태
    return re.sub(
        r"const\s+productId\s*=\s*\"[^\"]*\";",
        f'const productId = "{product_id}";',
        html,
        flags=re.MULTILINE,
    )


def _read_manifest(product_dir: Path) -> Dict[str, Any]:
    """outputs/<product_id>/manifest.json 읽기(없으면 빈 dict)."""
    try:
        p = product_dir / "manifest.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _count_files(dir_path: Path) -> int:
    """폴더 내 파일 수(하위 포함)."""
    if not dir_path.exists():
        return 0
    return sum(1 for p in dir_path.rglob("*") if p.is_file())


def _render_pricing_tiers(manifest: Dict[str, Any]) -> str:
    """랜딩에 삽입할 3-tier 가격/번들 블록 HTML."""
    base = float(manifest.get("price_usd") or 39)

    # 심리적 가격(끝자리를 9로)
    def _psych(x: float) -> int:
        x = int(round(x))
        # 29~79 범위를 벗어나면 clamp
        x = max(29, min(79, x))
        if x % 10 != 9:
            x = (x // 10) * 10 + 9
        return x

    p_basic = _psych(base)
    p_bundle = _psych(base + 20)
    p_pro = _psych(base + 40)

    counts = (
        manifest.get("quality", {}).get("counts", {})
        if isinstance(manifest.get("quality"), dict)
        else {}
    )
    assets = counts.get("assets_files", "?")
    bonus = counts.get("bonus_files", "?")
    promos = counts.get("promotion_files", "?")
    diagrams = counts.get("diagram_files", "?")

    return (
        '<div class="card">'
        "<h3>Choose your bundle</h3>"
        '<div class="row">'
        f'<div class="card" style="flex:1; min-width:220px"><h4>Basic</h4><div class="muted">$ {p_basic} USD</div>'
        "<ul>"
        "<li>Premium PDF + Markdown source</li>"
        "<li>Core diagrams + checklists</li>"
        "</ul></div>"
        f'<div class="card" style="flex:1; min-width:220px"><h4>Bundle</h4><div class="muted">$ {p_bundle} USD</div>'
        "<ul>"
        "<li>Everything in Basic</li>"
        "<li>Prompt pack + scripts + worksheets</li>"
        "<li>30-day promo calendar</li>"
        "</ul></div>"
        f'<div class="card" style="flex:1; min-width:220px"><h4>Pro</h4><div class="muted">$ {p_pro} USD</div>'
        "<ul>"
        "<li>Everything in Bundle</li>"
        "<li>Case study + benchmarks + troubleshooting matrix</li>"
        "<li>Support macros + launch plan</li>"
        "</ul></div>"
        "</div>"
        f'<p class="muted">Included assets detected: diagrams={diagrams}, assets={assets}, bonus={bonus}, promotions={promos}</p>'
        "</div>"
    )


def _render_proof_block(manifest: Dict[str, Any]) -> str:
    """랜딩에 삽입할 'proof' 블록 HTML."""
    q = manifest.get("quality", {}) if isinstance(manifest.get("quality"), dict) else {}
    score = q.get("score", "N/A")
    rubric = q.get("rubric", {})
    depth = rubric.get("depth", "N/A")
    structure = rubric.get("structure", "N/A")
    practicality = rubric.get("practicality", "N/A")
    clarity = rubric.get("clarity", "N/A")

    return (
        '<div class="card">'
        "<h3>What you get (proof)</h3>"
        "<ul>"
        "<li><b>Premium-quality</b> structure: Executive overview → foundation → implementation → case study → tools → checklists → advanced → troubleshooting → roadmap</li>"
        "<li><b>Quality audit</b> score: <code>"
        + str(score)
        + "</code> (depth "
        + str(depth)
        + ", structure "
        + str(structure)
        + ", practicality "
        + str(practicality)
        + ", clarity "
        + str(clarity)
        + ")</li>"
        "<li><b>Practical deliverables</b>: PDF, source MD, bonus pack, promotion pack</li>"
        "<li><b>Crypto-native</b>: payment gated download + deterministic build per product_id</li>"
        "</ul>"
        "</div>"
    )


def _write_landing(
    product_dir: Path, topic: str, product_id: str, meta: Dict[str, Any] | None = None
) -> Path:
#     """outputs/<product_id>/index.html 생성.
# 
#     - generator_module.generate(topic)로 기본 HTML 생성
#     - product_id 치환
#     - pricing/proof 블록 치환(placeholder 기반)
#     """
    html = generator_module.generate(topic)
    html = _patch_landing_product_id(html, product_id)

    manifest = _read_manifest(product_dir)
    # meta가 있으면 우선(동일 키 병합)
    if isinstance(meta, dict):
        manifest = {**manifest, **meta}

    # placeholder 치환
    tiers_html = _render_pricing_tiers(manifest)
    proof_html = _render_proof_block(manifest)
    html = html.replace("<!--PRICING_TIERS-->", tiers_html)
    html = html.replace("<!--PROOF_BLOCK-->", proof_html)

    path = product_dir / "index.html"
    path.write_text(html, encoding="utf-8")
    return path


def _ensure_clean_api(bundle_api_dir: Path) -> None:
    """deploy_bundle/api를 깨끗하게 구성한다."""
    if bundle_api_dir.exists():
        shutil.rmtree(bundle_api_dir, ignore_errors=True)
    (bundle_api_dir / "pay").mkdir(parents=True, exist_ok=True)

    # 필요한 서버리스 파일만 복사
    # - api/_vercel_common.py
    # - api/health.py
    # - api/pay/start.py, check.py, download.py
    shutil.copy2(
        PROJECT_ROOT / "api" / "_vercel_common.py", bundle_api_dir / "_vercel_common.py"
    )
    shutil.copy2(PROJECT_ROOT / "api" / "health.py", bundle_api_dir / "health.py")

    for name in ["start.py", "check.py", "download.py", "__init__.py"]:
        src = PROJECT_ROOT / "api" / "pay" / name
        if src.exists():
            shutil.copy2(src, bundle_api_dir / "pay" / name)


def create_deploy_bundle(run_dir: Path, product_id: str, landing_path: Path) -> Path:
    """Vercel 배포 단위 deploy_bundle 생성."""
    bundle_root = run_dir / product_id / "deploy_bundle"
    if bundle_root.exists():
        shutil.rmtree(bundle_root, ignore_errors=True)
    bundle_root.mkdir(parents=True, exist_ok=True)

    # 1) index.html
    shutil.copy2(landing_path, bundle_root / "index.html")

    # 2) vercel.json
    shutil.copy2(PROJECT_ROOT / "vercel.json", bundle_root / "vercel.json")

    # 3) api/
    _ensure_clean_api(bundle_root / "api")

    # 4) downloads/<product_id>/package.zip
    dst = bundle_root / "downloads" / product_id
    dst.mkdir(parents=True, exist_ok=True)

    pkg_src = OUTPUTS_DIR / product_id / "package.zip"
    if not pkg_src.exists():
        raise FileNotFoundError(f"package.zip not found: {pkg_src}")
    shutil.copy2(pkg_src, dst / "package.zip")

    return bundle_root


def deploy_to_vercel(bundle_root: Path) -> Dict[str, Any]:
    """Vercel CLI로 배포(선택)."""
    # vercel --prod --yes --confirm? (버전별 옵션이 다를 수 있어 최소 실행)
    cmd = ["vercel", "--prod", "--yes"]
    rc, out = _run_cmd(cmd, cwd=bundle_root)
    url = ""
    # 출력에서 URL 추출(단순 휴리스틱)
    for line in out.splitlines():
        if "https://" in line and "vercel.app" in line:
            url = line.strip()
            break
    return {"returncode": rc, "output": out, "url": url}


def main() -> int:
    load_dotenv(dotenv_path=str(PROJECT_ROOT / ".env"), override=False)
    load_dotenv(dotenv_path=str(PROJECT_ROOT / ".env.local"), override=False)

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--batch", type=int, default=1, help="how many products to generate"
    )
    ap.add_argument("--seed", type=str, default="", help="run seed for determinism")
    ap.add_argument("--topic", type=str, default="", help="fixed topic (optional)")
    ap.add_argument("--deploy", action="store_true", help="deploy to Vercel")
    args = ap.parse_args()

    run_seed = args.seed.strip() or _utc_compact()
    run_id = f"{_utc_compact()}-run"
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # 제품 메타 목록
    metas: List[Dict[str, Any]] = []

    # topic 고정이면 1개 생성 루프에서 topic을 고정
    if args.topic.strip():
        topic = args.topic.strip()
        for i in range(max(1, int(args.batch))):
            product_id = make_product_id(topic=topic, salt=f"{run_seed}:{i}")
            meta = generate_one(
                ProductConfig(
                    outputs_dir=OUTPUTS_DIR, topic=topic, product_id=product_id
                )
            )
            product_dir = OUTPUTS_DIR / product_id
            landing = _write_landing(
                product_dir=product_dir, topic=topic, product_id=product_id, meta=meta
            )
            promo_meta = generate_promotions(
                product_dir=product_dir,
                product_id=product_id,
                title=str(meta.get("title")),
                topic=str(meta.get("topic")),
                price_usd=float(meta.get("price_usd", 29.0)),
            )
            # Update manifest with promotions counts (so landing proof blocks match)
            try:
                mpath = product_dir / "manifest.json"
                if mpath.exists():
                    man = json.loads(mpath.read_text(encoding="utf-8"))
                    q = (
                        man.get("quality", {})
                        if isinstance(man.get("quality"), dict)
                        else {}
                    )
                    counts = (
                        q.get("counts", {}) if isinstance(q.get("counts"), dict) else {}
                    )
                    counts["promotion_files"] = _count_files(product_dir / "promotions")
                    q["counts"] = counts
                    man["quality"] = q
                    _atomic_write_json(mpath, man)
            except Exception:
                pass

            bundle_root = create_deploy_bundle(
                run_dir=run_dir, product_id=product_id, landing_path=landing
            )

            deploy_info = {"skipped": True}
            if args.deploy:
                deploy_info = deploy_to_vercel(bundle_root=bundle_root)

            metas.append(
                {
                    **meta,
                    "landing": str(landing),
                    "bundle_root": str(bundle_root),
                    "deploy": deploy_info,
                    "promotions": promo_meta,
                }
            )
    else:
        # batch_generate가 토픽 자동 선택 + 결정적 product_id 생성
        batch_metas = batch_generate(
            outputs_dir=OUTPUTS_DIR,
            n=int(args.batch),
            run_seed=run_seed,
            topics=DEFAULT_TOPICS,
        )
        for meta in batch_metas:
            product_id = str(meta.get("product_id"))
            topic = str(meta.get("topic"))
            product_dir = OUTPUTS_DIR / product_id
            landing = _write_landing(
                product_dir=product_dir, topic=topic, product_id=product_id, meta=meta
            )

            promo_meta = generate_promotions(
                product_dir=product_dir,
                product_id=product_id,
                title=str(meta.get("title")),
                topic=str(meta.get("topic")),
                price_usd=float(meta.get("price_usd", 29.0)),
            )
            bundle_root = create_deploy_bundle(
                run_dir=run_dir, product_id=product_id, landing_path=landing
            )

            deploy_info = {"skipped": True}
            if args.deploy:
                deploy_info = deploy_to_vercel(bundle_root=bundle_root)

            metas.append(
                {
                    **meta,
                    "landing": str(landing),
                    "bundle_root": str(bundle_root),
                    "deploy": deploy_info,
                    "promotions": promo_meta,
                }
            )

    report = {
        "run_id": run_id,
        "run_seed": run_seed,
        "created_at": _utc_compact(),
        "products": metas,
    }
    _atomic_write_json(run_dir / "report.json", report)

    print(f"OK RUN_DIR={run_dir}")
    print(f"REPORT={run_dir / 'report.json'}")
    if metas:
        print(f"PRODUCTS={len(metas)}")
        print(f"LATEST_PRODUCT_ID={metas[-1].get('product_id')}")
        print(f"LATEST_LANDING={metas[-1].get('landing')}")
        if isinstance(metas[-1].get("deploy"), dict) and metas[-1]["deploy"].get("url"):
            print(f"DEPLOY_URL={metas[-1]['deploy']['url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
