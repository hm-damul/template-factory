# -*- coding: utf-8 -*-
"""
product_factory.py

목적:
- "랜딩페이지만 있는 템플릿"이 아니라, 실제로 판매 가능한 디지털 제품을 자동 생성한다.
- 각 product_id 단위로 아래 산출물을 만든다.

산출물(필수):
- outputs/<product_id>/
    - product.pdf                 : 실제 가이드/이북(PDF)
    - manifest.json               : 메타데이터 + 체크섬(sha256)
    - package.zip                 : 판매/다운로드용 패키지(아래 포함)
    - assets/                     : 아이콘/이미지(가능한 범위)
    - bonus/                      : 체크리스트/프롬프트/템플릿/스크립트
    - promotions/                 : 홍보 자동 생성 결과(다른 모듈이 채움)

주의:
- 외부 LLM/API 없이도 "결정적(deterministic)"으로 재현 가능하도록 seed 기반 생성.
- 나중에 LLM을 붙이기 쉬운 구조(Topic -> Outline -> Sections)로 작성.

초보자 안내:
- 이 파일 하나만 실행하는 것이 아니라 auto_pilot.py가 이 모듈을 호출한다.
"""

from __future__ import annotations

import hashlib  # sha256 계산
import json  # manifest 저장
import random  # 결정적 생성
import textwrap  # 줄바꿈
import time  # created_at
import zipfile  # package.zip 생성
import requests  # 이미지 다운로드
import urllib.parse  # URL 인코딩
from dataclasses import dataclass  # 설정 구조체
from pathlib import Path  # 안전한 경로
from typing import Dict, List, Tuple  # 타입

# reportlab: PDF 생성 라이브러리 (requirements.txt에 포함)
from reportlab.lib.pagesizes import A4  # A4 사이즈
from reportlab.lib.units import mm  # mm 단위
from reportlab.pdfgen import canvas  # PDF 캔버스


def _sha256_file(path: Path) -> str:
    """파일의 SHA256 해시를 계산한다."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _atomic_write_json(path: Path, obj) -> None:
    """JSON을 원자적으로(atomic) 저장한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


def _slugify(text: str) -> str:
    """파일/폴더명으로 안전한 slug를 만든다."""
    s = (text or "").strip().lower()
    s = "".join(ch if ch.isalnum() else "-" for ch in s)
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-") or "product"


def _utc_iso() -> str:
    """UTC ISO 타임스탬프 문자열."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _seed_from_product_id(product_id: str) -> int:
    """product_id로부터 32비트 seed를 만든다(결정적)."""
    digest = hashlib.sha256(product_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big", signed=False)


DEFAULT_TOPICS: List[str] = [
    "Crypto Wallet Buyer Playbook: Privacy-First Digital Product Purchasing",
    "Global Merchant Crypto Checkout Blueprint (No Bank Friction)",
    "How to Sell High-Ticket Digital Products for Crypto (Ops + Security)",
    "Token-Gated Content + Revenue Automation for Web3 Communities",
    "Stablecoin Settlement Handbook for Cross-Border Solopreneurs",
    "Anti-Fraud & Chargeback-Free Sales System Using Crypto Payments",
    "Cold-Wallet Ops Manual for Digital Product Businesses",
    "Crypto-First Email + Funnel System for Passive Digital Product Sales",
    "SaaS Boilerplate for Crypto Payments (Next.js + Tailwind)",
    "AI Agent Monetization Guide: Selling Custom GPT Actions",
    "Digital Nomad Tax Haven Guide: Crypto-Friendly Jurisdictions",
    "Web3 Marketing Playbook: Community Growth & Tokenomics",
    "Zero-Knowledge Proofs for Beginners: Privacy in Blockchain",
    "DeFi Passive Income Strategies: Staking, Yield Farming, and Lending",
    "NFT Business Blueprint: Beyond the Hype to Real Utility",
    "DAO Governance 101: How to Launch and Manage a Decentralized Org",
]


@dataclass
class ProductConfig:
    """제품 생성 설정."""

    outputs_dir: Path  # outputs 경로
    topic: str  # 주제
    product_id: str  # 고유 id
    price_usd: float | None = None  # 기본 가격 (None이면 랜덤/동적 결정)
    currency: str = "usd"  # NOWPayments 기본 통화
    include_assets: bool = True  # assets 생성 여부


def _make_outline(rng: random.Random, topic: str) -> List[Tuple[str, List[str]]]:
    """토픽 기반으로 목차(섹션/불릿)를 만든다."""
    section_templates = [
        (
            "Executive Summary",
            [
                "Who this product is for",
                "What problem it solves in fiat ecosystems",
                "Why crypto buyers pay a premium",
            ],
        ),
        (
            "Threat Model & Privacy",
            [
                "What leaks (IP, email, on-chain heuristics)",
                "Operational security basics (OPSEC)",
                "Safer purchase workflow",
            ],
        ),
        (
            "Payment Architecture",
            [
                "Order lifecycle (pending → paid → fulfilled)",
                "Provider selection (NOWPayments default)",
                "Edge cases (timeouts, underpayment, overpayment)",
            ],
        ),
        (
            "Fulfillment System",
            [
                "Gated download logic",
                "Signed links vs server-side streaming",
                "Audit trail & receipts",
            ],
        ),
        (
            "Growth & Promotion",
            [
                "Evergreen promotion assets",
                "Channel-specific posting templates",
                "SEO checklist for product pages",
            ],
        ),
        (
            "Runbook",
            [
                "Daily operations checklist",
                "Incident handling (webhook failure, provider outage)",
                "Data backup and migration",
            ],
        ),
    ]

    rng.shuffle(section_templates)
    n = 6 if rng.random() > 0.4 else 5
    picked = section_templates[:n]

    outline: List[Tuple[str, List[str]]] = []
    outline.append(
        (
            f"Guide Topic: {topic}",
            [
                "What you will build",
                "The exact deliverables",
                "How to apply it immediately",
            ],
        )
    )
    outline.extend(picked)
    outline.append(
        (
            "Appendix: Templates & Prompts",
            [
                "Copy/paste checklists",
                "Promotion pack prompts",
                "Quick-start scripts",
            ],
        )
    )
    return outline


def _render_paragraph(rng: random.Random, bullets: List[str]) -> str:
    """섹션 텍스트를 만든다(결정적)."""
    starter = [
        "This section is designed for operators who value repeatability and security.",
        "If you treat crypto payments like 'just another checkout', you will leak money and privacy.",
        "The goal is to make the purchase flow boring: predictable, auditable, and hard to exploit.",
        "High-ticket digital products sell when the buyer feels safe and the seller fulfills instantly.",
    ]
    mid = [
        "Use a single source of truth for orders and always verify paid status server-side.",
        "Prefer deterministic packaging: stable filenames, stable checksums, stable manifests.",
        "Avoid unnecessary client-side secrets; anything shipped to the browser is public.",
        "Make failure modes explicit: pending, expired, paid, refunded, underpaid, overpaid.",
    ]
    end = [
        "Implementation detail: keep your API surface minimal and consistent across local and deployed environments.",
        "Operational detail: log everything you need to debug, and nothing you don't want to leak.",
        "Commercial detail: crypto buyers often accept premium pricing for privacy and instant delivery.",
    ]

    rng.shuffle(starter)
    rng.shuffle(mid)
    rng.shuffle(end)

    parts: List[str] = []
    parts.append(f"{starter[0]} {starter[1]}")
    parts.append(f"{mid[0]} {mid[1]}")
    parts.append(f"{end[0]}")
    for b in bullets:
        parts.append(f"- {b}: {mid[2]}")
    return "\n".join(parts).strip()


def build_product_text(product_id: str, topic: str) -> Dict[str, object]:
    """제품 내용을 텍스트 데이터로 만든다."""
    seed = _seed_from_product_id(product_id)
    rng = random.Random(seed)

    outline = _make_outline(rng, topic)

    sections = []
    for h, bullets in outline:
        body = _render_paragraph(rng, bullets)
        sections.append({"h": h, "body": body})

    title = topic.strip() or "Crypto Digital Product"
    return {
        "title": title,
        "topic": topic,
        "product_id": product_id,
        "sections": sections,
    }


def _pdf_draw_wrapped_text(
    c: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    max_width: float,
    leading: float,
) -> float:
#     """주어진 영역에 텍스트를 자동 줄바꿈하여 그린다."""
    approx_chars = max(30, int(max_width / 6))
    lines: List[str] = []
    for para in (text or "").splitlines():
        if para.strip().startswith("- "):
            lines.extend(textwrap.wrap(para, width=max(20, approx_chars - 6)))
        else:
            lines.extend(textwrap.wrap(para, width=approx_chars))
        lines.append("")

    for line in lines:
        if y < 20 * mm:
            c.showPage()
            c.setFont("Helvetica", 11)
            y = 280 * mm
        c.drawString(x, y, line)
        y -= leading

    return y


def write_product_pdf(pdf_path: Path, content: Dict[str, object]) -> None:
    """content를 기반으로 product.pdf를 만든다."""
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(pdf_path), pagesize=A4)

    c.setFont("Helvetica-Bold", 22)
    c.drawString(20 * mm, 270 * mm, str(content.get("title", "Crypto Product")))
    c.setFont("Helvetica", 12)
    c.drawString(20 * mm, 260 * mm, f"product_id: {content.get('product_id', '')}")
    c.drawString(20 * mm, 252 * mm, f"created_at: {_utc_iso()}")
    c.drawString(
        20 * mm,
        244 * mm,
        "Positioning: High-value digital product for crypto-wallet buyers",
    )

    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, 230 * mm, "Diagram: Order → Payment → Delivery")

    y0 = 215 * mm
    box_w = 50 * mm
    box_h = 12 * mm
    x0 = 20 * mm

    for i, label in enumerate(["Order", "Paid", "Download"]):
        x = x0 + i * (box_w + 10 * mm)
        c.rect(x, y0, box_w, box_h)
        c.setFont("Helvetica", 11)
        c.drawString(x + 5 * mm, y0 + 3 * mm, label)
        if i < 2:
            c.line(x + box_w, y0 + box_h / 2, x + box_w + 10 * mm, y0 + box_h / 2)
            c.line(
                x + box_w + 8 * mm,
                y0 + box_h / 2 + 2,
                x + box_w + 10 * mm,
                y0 + box_h / 2,
            )
            c.line(
                x + box_w + 8 * mm,
                y0 + box_h / 2 - 2,
                x + box_w + 10 * mm,
                y0 + box_h / 2,
            )

    c.showPage()

    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, 280 * mm, "Contents")
    y = 270 * mm

    for sec in content.get("sections", []):
        h = str(sec.get("h", "Section"))
        body = str(sec.get("body", ""))

        if y < 40 * mm:
            c.showPage()
            c.setFont("Helvetica", 11)
            y = 280 * mm

        c.setFont("Helvetica-Bold", 14)
        c.drawString(20 * mm, y, h)
        y -= 8 * mm

        c.setFont("Helvetica", 11)
        y = _pdf_draw_wrapped_text(
            c=c,
            text=body,
            x=20 * mm,
            y=y,
            max_width=170 * mm,
            leading=5.5 * mm,
        )
        y -= 4 * mm

    c.save()


def write_assets(assets_dir: Path, product_id: str, topic: str) -> str:
    """assets 폴더에 아이콘(SVG) 및 커버 이미지(JPG)를 만든다."""
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
        f"Assets for {product_id}\nTopic: {topic}\n\n- icon_wallet_lock.svg: simple vector icon\n",
        encoding="utf-8",
    )

    # 커버 이미지 생성 (Pollinations AI 사용)
    cover_filename = "cover.jpg"
    cover_path = assets_dir / cover_filename
    screenshot_url = ""

    try:
        encoded_topic = urllib.parse.quote(topic)
        image_url = f"https://image.pollinations.ai/prompt/digital%20product%20cover%20{encoded_topic}?width=800&height=600&nologo=true"
        print(f"Downloading cover image for {topic}...")
        response = requests.get(image_url, timeout=15)
        if response.status_code == 200:
            cover_path.write_bytes(response.content)
            screenshot_url = f"assets/{cover_filename}"
            print(f"Saved cover image to {cover_path}")
        else:
            print(f"Failed to download image: {response.status_code}")
    except Exception as e:
        print(f"Error downloading cover image: {e}")

    # Fallback if download failed
    if not screenshot_url and not cover_path.exists():
        try:
            fallback_url = f"https://placehold.co/800x600/png?text={urllib.parse.quote(topic[:20])}"
            r = requests.get(fallback_url, timeout=10)
            if r.status_code == 200:
                cover_path.write_bytes(r.content)
                screenshot_url = f"assets/{cover_filename}"
        except Exception as e:
            print(f"Warning: Failed to download fallback image: {e}")

    return screenshot_url
# 
# 
# def write_bonus(bonus_dir: Path, product_id: str, topic: str) -> None:
#     """bonus 폴더에 체크리스트/프롬프트/스크립트를 만든다."""
    bonus_dir.mkdir(parents=True, exist_ok=True)

    (bonus_dir / "checklist.md").write_text(
        f"""# Daily Operations Checklist (Crypto Digital Product Factory)

product_id: {product_id}
topic: {topic}

## Security / OPSEC
- [ ] Do not log secrets (API keys, wallet seeds) anywhere.
- [ ] Verify paid status server-side before any download.
- [ ] Keep an audit trail: order_id, product_id, amount, currency, timestamps.

## Sales / Delivery
- [ ] Product page loads and calls /api/pay/start via POST.
- [ ] /api/pay/check transitions pending -> paid (provider or simulated).
- [ ] /api/pay/download returns package.zip only after paid.

## Backups
- [ ] Backup outputs/<product_id>/ and data/orders.json
- [ ] Keep a hash list (manifest.json) for integrity verification.
""",
        encoding="utf-8",
    )

    (bonus_dir / "prompts.txt").write_text(
        f"""# Copy/Paste Prompts (for later LLM upgrade)

## Product upgrade prompt
You are a crypto commerce operator. Expand this guide into a high-ticket product:
- Topic: {topic}
- Target buyers: privacy-first crypto wallet users
- Must include: threat model, payment flow, delivery gating, ops runbook, promotion assets

Output: markdown sections, checklists, scripts, diagrams.

## Promotion pack prompt
Generate channel-specific posts:
- X/Twitter: 5 variations
- Reddit: 3 variations
- LinkedIn: 2 variations
- Email: 1 short newsletter
- SEO meta + keywords

Focus on: privacy, global payments, instant delivery, chargeback-free.
""",
        encoding="utf-8",
    )

    (bonus_dir / "quick_verify_manifest.py").write_text(
#         """# -*- coding: utf-8 -*-
# \"\"\"
# quick_verify_manifest.py
# 
# 목적:
# - manifest.json의 sha256 체크섬이 실제 파일과 일치하는지 빠르게 검증한다.
# 
# 실행(Windows PowerShell):
#   python bonus\\quick_verify_manifest.py ..\\manifest.json
# \"\"\"
# 
# import hashlib
# import json
# import sys
# from pathlib import Path
# 
# 
# def sha256_file(path: Path) -> str:
#     h = hashlib.sha256()
#     with path.open(\"rb\") as f:
#         for chunk in iter(lambda: f.read(1024 * 1024), b\"\"):
#             h.update(chunk)
#     return h.hexdigest()
# 
# 
# def main() -> int:
#     if len(sys.argv) < 2:
#         print(\"Usage: python quick_verify_manifest.py <path-to-manifest.json>\")
#         return 2
# 
#     manifest_path = Path(sys.argv[1]).resolve()
#     base_dir = manifest_path.parent
# 
#     data = json.loads(manifest_path.read_text(encoding=\"utf-8\"))
#     checksums = data.get(\"checksums\", {})
# 
#     ok = True
#     for rel, expected in checksums.items():
#         p = (base_dir / rel).resolve()
#         if not p.exists():
#             print(f\"[MISSING] {rel}\")
#             ok = False
#             continue
#         actual = sha256_file(p)
#         if actual != expected:
#             print(f\"[BAD] {rel}\\n  expected: {expected}\\n  actual:   {actual}\")
#             ok = False
#         else:
#             print(f\"[OK] {rel}\")
#     return 0 if ok else 1
# 
# 
# if __name__ == \"__main__\":
#     raise SystemExit(main())
# """,
        encoding="utf-8",
    )


def build_package_zip(product_dir: Path, package_zip_path: Path) -> None:
    """product_dir 내부를 package.zip으로 묶는다."""
    package_zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(package_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(product_dir.rglob("*")):
            if p.is_dir():
                continue
            rel = p.relative_to(product_dir).as_posix()
            z.write(p, rel)


def write_manifest(product_dir: Path, meta: Dict[str, object]) -> None:
    """manifest.json을 생성한다(sha256 포함)."""
    checksums: Dict[str, str] = {}
    for p in sorted(product_dir.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(product_dir).as_posix()
        if rel == "manifest.json":
            continue
        checksums[rel] = _sha256_file(p)

    manifest = {
        "schema_version": 1,
        "title": meta.get("title"),
        "topic": meta.get("topic"),
        "product_id": meta.get("product_id"),
        "created_at": meta.get("created_at"),
        "price_usd": meta.get("price_usd"),
        "currency": meta.get("currency"),
        "screenshot_url": meta.get("screenshot_url"),
        "checksums": checksums,
    }
    _atomic_write_json(product_dir / "manifest.json", manifest)


def generate_one(cfg: ProductConfig) -> Dict[str, object]:
    """제품 1개를 생성하고 outputs/<product_id>/ 에 저장한다."""
    product_dir = cfg.outputs_dir / cfg.product_id
    product_dir.mkdir(parents=True, exist_ok=True)

    content = build_product_text(product_id=cfg.product_id, topic=cfg.topic)

    pdf_path = product_dir / "product.pdf"
    write_product_pdf(pdf_path=pdf_path, content=content)

    screenshot_url = ""
    if cfg.include_assets:
        screenshot_url = write_assets(product_dir / "assets", cfg.product_id, cfg.topic)

    write_bonus(product_dir / "bonus", cfg.product_id, cfg.topic)

    (product_dir / "promotions").mkdir(parents=True, exist_ok=True)

    package_zip_path = product_dir / "package.zip"
    build_package_zip(product_dir=product_dir, package_zip_path=package_zip_path)

    meta = {
        "title": content["title"],
        "topic": cfg.topic,
        "product_id": cfg.product_id,
        "created_at": _utc_iso(),
        "price_usd": cfg.price_usd,
        "currency": cfg.currency,
        "screenshot_url": screenshot_url,
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
#     """n개 제품을 배치로 생성한다."""
    outputs_dir.mkdir(parents=True, exist_ok=True)

    seed_int = int(hashlib.sha256(run_seed.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed_int)

    topic_list = topics or DEFAULT_TOPICS

    metas: List[Dict[str, object]] = []
    for i in range(max(1, int(n))):
        topic = topic_list[rng.randrange(0, len(topic_list))]
        product_id = make_product_id(topic=topic, salt=f"{run_seed}:{i}")
        meta = generate_one(
            ProductConfig(
                outputs_dir=outputs_dir,
                topic=topic,
                product_id=product_id,
                price_usd=price_usd,
                currency=currency,
                include_assets=True,
            )
        )
        metas.append(meta)

    return metas
