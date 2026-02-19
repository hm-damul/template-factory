# -*- coding: utf-8 -*-
"""
product_factory.py (PREMIUM UPGRADE)

목적:
- "랜딩페이지만 있는 템플릿"이 아니라, 실제로 판매 가능한 프리미엄 디지털 제품을 자동 생성한다.
- 각 product_id 단위로 아래 산출물을 만든다.

산출물(필수):
- outputs/<product_id>/
    - product.pdf                 : 프리미엄 PDF (타이틀/TOC/콜아웃/다이어그램/푸터)
    - product.md                  : 동일 콘텐츠의 markdown 소스(검증/재사용/업데이트 용)
    - manifest.json               : 메타데이터 + 체크섬(sha256)
    - package.zip                 : 판매/다운로드용 패키지(아래 포함)
    - assets/
        - icon_wallet_lock.svg
        - diagrams/               : funnel_flow.png, system_architecture.png, process_steps.png (+ SVG fallback 가능)
    - bonus/                      : 체크리스트/프롬프트팩/스크립트/워크시트(고품질)
    - promotions/                 : 홍보 자동 생성 결과(다른 모듈이 채움)

설계 원칙:
- 외부 LLM/API 없이도 "결정적(deterministic)"으로 재현 가능하도록 product_id 기반 seed 생성.
- 프리미엄 구조(9개 섹션) + 품질 감사(Quality Audit) 루프로 "얕은 요약"을 제거.

연결:
- auto_pilot.py가 이 모듈의 generate_one()/batch_generate()를 호출한다.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

from diagram_generator import DiagramResult, generate_diagrams
from premium_bonus_generator import build_bonus_package

# --- Premium modules ---
from premium_content_engine import PremiumProduct, generate_premium_product, to_markdown
from premium_pdf_builder import build_premium_pdf
from quality_audit import score_section

# -----------------------------
# Defaults / Config
# -----------------------------

DEFAULT_TOPICS = [
    "Crypto Checkout + Instant Digital Delivery Blueprint",
    "Privacy-First Digital Product Sales Funnel (Crypto Payments)",
    "Web3 Token-Gated Content Delivery System",
    "Chargeback-Free Digital Product Storefront (Stablecoins)",
    "Crypto Payment Landing Page + Conversion Optimization Playbook",
]


@dataclass
class ProductConfig:
    outputs_dir: Path
    topic: str
    product_id: str
    price_usd: float = 29.0
    currency: str = "usd"
    include_assets: bool = True


# -----------------------------
# Determinism helpers
# -----------------------------


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _atomic_write_json(path: Path, obj: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _utc_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "product"


# -----------------------------
# Asset generation
# -----------------------------


def write_assets(
    assets_dir: Path, product_id: str, topic: str, product: PremiumProduct
) -> DiagramResult:
#     """
#     assets 폴더:
#     - 최소 아이콘(SVG)
#     - diagrams/ (PNG 우선, 실패 시 SVG fallback)
#     """
    assets_dir.mkdir(parents=True, exist_ok=True)

    svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='256' height='256' viewBox='0 0 256 256'>
  <rect x='20' y='70' width='216' height='140' rx='16' fill='#111'/>
  <rect x='36' y='92' width='184' height='96' rx='12' fill='#222'/>
  <circle cx='192' cy='140' r='10' fill='#7CFFB2'/>
  <rect x='90' y='26' width='76' height='64' rx='12' fill='#111'/>
  <rect x='104' y='42' width='48' height='46' rx='10' fill='#222'/>
  <text x='128' y='245' font-size='12' text-anchor='middle' fill='#666'>{product_id}</text>
</svg>
"""
    (assets_dir / "icon_wallet_lock.svg").write_text(svg, encoding="utf-8")

    (assets_dir / "README.txt").write_text(
        f"Assets for {product_id}\nTopic: {topic}\n\n- icon_wallet_lock.svg: simple vector icon\n- diagrams/: generated visuals\n",
        encoding="utf-8",
    )

    diagrams_dir = assets_dir / "diagrams"
    result = generate_diagrams(diagrams_dir=diagrams_dir, meta=product.meta)

    # save a small log
    log_lines: List[str] = []
    log_lines.append("diagram_generation_log")
    log_lines.append(f"ok={result.ok}")
    for k, p in result.diagrams.items():
        log_lines.append(f"png:{k}={p.name}")
    for k, p in result.fallbacks_svg.items():
        log_lines.append(f"svg_fallback:{k}={p.name}")
    for e in result.errors:
        log_lines.append(f"error:{e}")
    (diagrams_dir / "generation.log").write_text(
        "\n".join(log_lines) + "\n", encoding="utf-8"
    )

    return result


# -----------------------------
# Bonus generation (premium)
# -----------------------------


def write_bonus(bonus_dir: Path, product: PremiumProduct) -> None:
    """
    premium_bonus_generator 기반 고품질 보너스 생성.
    """
    res = build_bonus_package(bonus_dir=bonus_dir, product=product)
    # bonus 생성 실패는 "제품 전체 실패"로 보지 않고, 파일로 로그만 남긴다.
    if not res.ok:
        (bonus_dir / "bonus_errors.log").write_text(
            "\n".join(res.errors) + "\n", encoding="utf-8"
        )


# -----------------------------
# Package / Manifest
# -----------------------------


def build_package_zip(product_dir: Path, package_zip_path: Path) -> None:
    """
    product_dir 내부를 package.zip으로 묶는다.
    - outputs/<product_id>/ 기준 상대경로로 zip
    """
    package_zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(package_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(product_dir.rglob("*")):
            if p.is_dir():
                continue
            rel = p.relative_to(product_dir).as_posix()
            z.write(p, rel)


def write_manifest(product_dir: Path, meta: Dict[str, object]) -> None:
    """manifest.json 생성(sha256 체크섬 포함)."""
    checksums: Dict[str, str] = {}
    for p in sorted(product_dir.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(product_dir).as_posix()
        if rel == "manifest.json":
            continue
        checksums[rel] = _sha256_file(p)

    manifest = {
        "schema_version": 2,
        "title": meta.get("title"),
        "topic": meta.get("topic"),
        "product_id": meta.get("product_id"),
        "created_at": meta.get("created_at"),
        "price_usd": meta.get("price_usd"),
        "currency": meta.get("currency"),
        "checksums": checksums,
        "quality": meta.get("quality", {}),
    }
    _atomic_write_json(product_dir / "manifest.json", manifest)


def _count_files(p: Path) -> int:
    """폴더 내 파일 수(하위 포함)."""
    if not p.exists():
        return 0
    return sum(1 for x in p.rglob("*") if x.is_file())


# -----------------------------
# Quality Control Loop
# -----------------------------


def _quality_audit_product(
    product: PremiumProduct, threshold: int = 80, max_regens_per_section: int = 2
) -> Tuple[PremiumProduct, Dict[str, Any]]:
#     """
#     섹션별 품질 점수 계산 후 기준 미달이면 "해당 섹션만" 결정적으로 재생성한다.
# 
#     결정성 보장 방법:
#     - 재생성 시에도 product_id 기반 seed + (section_key, attempt) salt를 사용한다.
#     - 동일 product_id에 대해 동일 threshold/max_regens를 사용하면 결과는 항상 동일하다.
# 
#     구현:
#     - premium_content_engine.generate_premium_product는 전체를 생성한다.
#       여기서는 "섹션만" 교체가 필요하므로, 전체를 재생성하되 섹션별 교체를 안정적으로 수행한다.
#     """
    # NOTE: 섹션별 독립 재생성을 위해 "topic은 동일"하고 "salted product_id"로 생성한 섹션을 교체한다.
    #       product_id 자체를 바꾸면 산출물 경로가 바뀌므로, 내부적으로만 salted id를 사용한다.

    quality_report: Dict[str, Any] = {"threshold": threshold, "sections": {}}
    new_sections = list(product.sections)

    for idx, sec in enumerate(product.sections):
        audit = score_section(sec)
        quality_report["sections"][sec.key] = {
            "score": audit.score,
            "ok": audit.ok,
            "details": audit.details,
        }

        if audit.ok:
            continue

        # attempt regeneration up to max
        for attempt in range(1, max_regens_per_section + 1):
            salted = f"{product.product_id}::regen::{sec.key}::{attempt}"
            regen_prod = generate_premium_product(
                product_id=salted, topic=product.topic
            )
            # find the same key section
            regen_sec = next((s for s in regen_prod.sections if s.key == sec.key), None)
            if regen_sec is None:
                continue
            audit2 = score_section(regen_sec)
            quality_report["sections"][sec.key][f"regen_attempt_{attempt}"] = {
                "score": audit2.score,
                "ok": audit2.ok,
                "details": audit2.details,
            }
            if audit2.ok or audit2.score > audit.score:
                # accept improvement (even if still below threshold, prefer best found)
                new_sections[idx] = regen_sec
                audit = audit2
                quality_report["sections"][sec.key]["final_score"] = audit2.score
                quality_report["sections"][sec.key]["final_ok"] = audit2.ok
            if audit2.ok:
                break

    # rebuild product object with new sections
    upgraded = PremiumProduct(
        product_id=product.product_id,
        topic=product.topic,
        title=product.title,
        subtitle=product.subtitle,
        audience=product.audience,
        price_band=product.price_band,
        sections=new_sections,
        toc=[(s.key, s.title) for s in new_sections],
        meta=product.meta,
    )
    # overall score (average)
    scores = [
        quality_report["sections"][k]["score"]
        for k in quality_report["sections"].keys()
    ]
    quality_report["overall_avg_score"] = round(sum(scores) / max(1, len(scores)), 1)
    return upgraded, quality_report


# -----------------------------
# Main generation API
# -----------------------------


def generate_one(cfg: ProductConfig) -> Dict[str, object]:
    """
    제품 1개를 생성하고 outputs/<product_id>/ 에 저장한다.

    반환 meta:
      - title/topic/product_id/created_at/price_usd/currency
      - quality report summary
    """
    product_dir = cfg.outputs_dir / cfg.product_id
    product_dir.mkdir(parents=True, exist_ok=True)

    # 1) Generate premium content (deterministic)
    product = generate_premium_product(product_id=cfg.product_id, topic=cfg.topic)

    # 2) Quality control loop (regenerate weak sections)
    product, quality_report = _quality_audit_product(
        product, threshold=80, max_regens_per_section=2
    )

    # 3) Save markdown source for transparency/reuse
    md_path = product_dir / "product.md"
    md_path.write_text(to_markdown(product), encoding="utf-8")

    # 4) Assets + diagrams
    diagrams_result: DiagramResult | None = None
    if cfg.include_assets:
        diagrams_result = write_assets(
            assets_dir=product_dir / "assets",
            product_id=cfg.product_id,
            topic=cfg.topic,
            product=product,
        )

    # 5) Premium PDF layout (platypus)
    pdf_path = product_dir / "product.pdf"
    pdf_res = build_premium_pdf(
        pdf_path=pdf_path, product=product, diagrams=diagrams_result
    )
    if not pdf_res.ok:
        (product_dir / "pdf_errors.log").write_text(
            "\n".join(pdf_res.errors) + "\n", encoding="utf-8"
        )

    # 6) Bonus package
    write_bonus(bonus_dir=product_dir / "bonus", product=product)

    # promotions dir (filled by promotion_factory)
    (product_dir / "promotions").mkdir(parents=True, exist_ok=True)

    # 7) Package zip
    package_zip_path = product_dir / "package.zip"
    build_package_zip(product_dir=product_dir, package_zip_path=package_zip_path)

    # 8) Counts for landing 'proof blocks'
    # NOTE: promotions 파일은 auto_pilot에서 생성하므로 여기서는 0일 수 있다.
    quality_report.setdefault("counts", {})
    quality_report["counts"]["assets_files"] = _count_files(product_dir / "assets")
    quality_report["counts"]["diagram_files"] = _count_files(
        product_dir / "assets" / "diagrams"
    )
    quality_report["counts"]["bonus_files"] = _count_files(product_dir / "bonus")
    quality_report["counts"]["promotion_files"] = _count_files(
        product_dir / "promotions"
    )

    meta: Dict[str, object] = {
        "title": product.title,
        "topic": cfg.topic,
        "product_id": cfg.product_id,
        "created_at": _utc_iso(),
        "price_usd": cfg.price_usd,
        "currency": cfg.currency,
        "quality": quality_report,
    }
    write_manifest(product_dir=product_dir, meta=meta)
    return meta


def pick_topic(seed: int | None = None, topics: List[str] | None = None) -> str:
    """토픽을 자동 선택한다(설정 가능)."""
    tlist = topics or DEFAULT_TOPICS
    rng = random.Random(seed if seed is not None else int(time.time()))
    return rng.choice(tlist)


def make_product_id(topic: str, salt: str) -> str:
    """topic + salt로 product_id를 만든다."""
    base = _slugify(topic)[:32]
    suffix = hashlib.sha256((topic + "|" + salt).encode("utf-8")).hexdigest()[:8]
    return f"{base}-{suffix}"


def batch_generate(
    outputs_dir: Path,
    n: int,
    run_seed: str,
    topics: List[str] | None = None,
    price_usd: float = 29.0,
    currency: str = "usd",
) -> List[Dict[str, object]]:
#     """
#     N개 제품을 생성한다.
#     - 토픽 자동 선택 + 결정적 product_id 생성
#     - 각 제품은 generate_one으로 생성됨(프리미엄 파이프라인 포함)
#     """
    outputs_dir.mkdir(parents=True, exist_ok=True)

    metas: List[Dict[str, object]] = []
    tlist = topics or DEFAULT_TOPICS

    # run_seed 고정 => batch 결과도 결정적
    rng = random.Random(
        int(hashlib.sha256(run_seed.encode("utf-8")).hexdigest()[:8], 16)
    )

    for i in range(max(1, int(n))):
        topic = tlist[rng.randrange(0, len(tlist))]
        product_id = make_product_id(topic=topic, salt=f"{run_seed}:{i}")
        meta = generate_one(
            ProductConfig(
                outputs_dir=outputs_dir,
                topic=topic,
                product_id=product_id,
                price_usd=price_usd,
                currency=currency,
            )
        )
        metas.append(meta)

    return metas


# -----------------------------
# CLI (optional)
# -----------------------------


def main() -> int:
    """
    단독 실행용(디버그):
      python product_factory.py
    """
    out = Path("outputs")
    topic = pick_topic()
    product_id = make_product_id(topic, salt=_utc_iso())
    meta = generate_one(
        ProductConfig(outputs_dir=out, topic=topic, product_id=product_id)
    )
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
