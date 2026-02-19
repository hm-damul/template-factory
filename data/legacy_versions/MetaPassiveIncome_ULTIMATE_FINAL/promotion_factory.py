# -*- coding: utf-8 -*-
"""
promotion_factory.py

목적:
- 제품별 홍보 문구를 자동 생성한다(외부 API 없이도 기본 동작).
- 생성 결과를 outputs/<product_id>/promotions/ 아래에 저장한다.
- promo_pack.zip 도 함께 만든다.

생성물:
- x_posts.txt           : X/Twitter용 5개
- reddit_posts.txt      : Reddit용 3개
- linkedin_posts.txt    : LinkedIn용 2개
- newsletter_email.txt  : 짧은 이메일 뉴스레터 1개
- seo.txt               : SEO 메타 + 키워드
- ready_to_publish.json : 대시보드에서 "Publish" 누르면 생성(기본은 파일만)
- promo_pack.zip        : promotions 폴더 압축

옵션 배포(안전 기본값):
- X/Telegram/Discord 등의 실제 전송은 "키가 있을 때만" 시도하고,
  키가 없으면 파일만 만든다.
"""

from __future__ import annotations

import hashlib  # 결정적 seed
import json  # ready_to_publish.json
import random  # 텍스트 변형
import time  # 타임스탬프
import zipfile  # promo_pack.zip
from pathlib import Path  # 경로
from typing import Dict, List  # 타입


def _utc_iso() -> str:
    """UTC ISO 문자열."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _seed_from_product_id(product_id: str) -> int:
    """product_id로부터 seed를 만든다."""
    digest = hashlib.sha256(product_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big", signed=False)


def _write(path: Path, text: str) -> None:
    """텍스트 파일 저장."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def _atomic_write_json(path: Path, obj) -> None:
    """JSON 원자 저장."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


def generate_promotions(
    product_dir: Path, product_id: str, title: str, topic: str, price_usd: float
) -> Dict[str, object]:
#     """
#     promotions 폴더에 홍보 텍스트를 생성한다.
#     반환: meta(직렬화 가능한 dict)
#     """
    promo_dir = product_dir / "promotions"
    promo_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(_seed_from_product_id(product_id))

    hooks = [
        "chargeback-free",
        "privacy-first",
        "instant delivery",
        "global payments",
        "no bank friction",
    ]
    rng.shuffle(hooks)

    angle = hooks[0]
    tag = "#crypto #bitcoin #web3 #payments"

    x_posts: List[str] = []
    for i in range(5):
        line = (
            f"{title} — a high-ticket style digital product for wallet buyers. "
            f"Angle: {angle}. Price: ${price_usd:.0f}. "
            f"Buy with crypto → instant download. {tag}"
        )
        if i % 2 == 1:
            line = (
                f"If you prefer paying with a wallet (no card trail), this is for you: {title}. "
                f"{angle}. ${price_usd:.0f}. {tag}"
            )
        x_posts.append(line)

    reddit_posts: List[str] = []
    for i in range(3):
        reddit_posts.append(
            "\n".join(
                [
                    f"Title: {title} (pay with crypto, instant download)",
                    "\nBody:",
                    f"I built a practical guide for people who prefer wallet payments: {topic}.",
                    "It covers OPSEC, order lifecycle, and delivery gating (pending → paid → download).",
                    f"Price: ${price_usd:.0f}. If you're into privacy + global payments, it should help.",
                    "(No affiliate links; it's a direct download product.)",
                ]
            )
        )

    linkedin_posts: List[str] = []
    linkedin_posts.append(
        "\n".join(
            [
                "Digital products + crypto checkout can be a clean alternative to card rails.",
                f"I packaged a guide: {title}.",
                "Focus: privacy-first buyer experience, deterministic fulfillment, and an ops runbook.",
                f"Price: ${price_usd:.0f}. Wallet buyers get instant delivery.",
            ]
        )
    )
    linkedin_posts.append(
        "\n".join(
            [
                "Chargebacks are a hidden tax on digital products.",
                f"This guide shows a minimal, auditable payment+delivery pipeline: {title}.",
                "Built for global buyers who prefer crypto wallets.",
            ]
        )
    )

    newsletter = "\n".join(
        [
            f"Subject: New crypto-only digital product — {title}",
            "",
            "If you prefer paying with a crypto wallet (privacy + global reach), I released a new product:",
            f"- {title}",
            f"- Price: ${price_usd:.0f}",
            "- Instant download after payment",
            "",
            "It includes a PDF guide, checklists, and templates for a repeatable payment→delivery flow.",
            "",
            "Reply to this email if you want a discount code for early buyers.",
        ]
    )

    seo = "\n".join(
        [
            f"meta_description: {title}. High-value guide for crypto wallet buyers: privacy-first purchase, instant delivery, global payments.",
            "keywords:",
            "- crypto digital product",
            "- pay with crypto wallet",
            "- instant download",
            "- privacy-first checkout",
            "- chargeback-free payments",
            "- global payments",
        ]
    )

    _write(promo_dir / "x_posts.txt", "\n\n---\n\n".join(x_posts))
    _write(promo_dir / "reddit_posts.txt", "\n\n---\n\n".join(reddit_posts))
    _write(promo_dir / "linkedin_posts.txt", "\n\n---\n\n".join(linkedin_posts))
    _write(promo_dir / "newsletter_email.txt", newsletter)
    _write(promo_dir / "seo.txt", seo)

    # promo_pack.zip 생성
    promo_zip = promo_dir / "promo_pack.zip"
    with zipfile.ZipFile(promo_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(promo_dir.glob("*.txt")):
            z.write(p, p.name)

    meta = {
        "product_id": product_id,
        "created_at": _utc_iso(),
        "files": [
            "x_posts.txt",
            "reddit_posts.txt",
            "linkedin_posts.txt",
            "newsletter_email.txt",
            "seo.txt",
            "promo_pack.zip",
        ],
    }
    _atomic_write_json(promo_dir / "promotion_manifest.json", meta)

    return meta


def mark_ready_to_publish(product_dir: Path, product_id: str) -> Path:
    """대시보드에서 Publish 눌렀을 때 기본 동작: ready_to_publish.json 생성."""
    promo_dir = product_dir / "promotions"
    promo_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "product_id": product_id,
        "created_at": _utc_iso(),
        "status": "ready",
        "note": "No API keys configured. This file indicates the product is ready to publish.",
    }
    path = promo_dir / "ready_to_publish.json"
    _atomic_write_json(path, payload)
    return path


import os  # env keys

import requests  # optional webhook posting


def _safe_post_json(url: str, payload: dict) -> bool:
    """웹훅 POST (실패해도 크래시하지 않음)."""
    try:
        r = requests.post(url, json=payload, timeout=10)
        return 200 <= int(r.status_code) < 300
    except Exception:
        return False


def publish_via_webhooks_safely(product_id: str) -> Dict[str, object]:
    """
    안전 기본값:
    - 키가 없으면 no-op
    - 있으면 Telegram/Discord webhook으로 1개 홍보 문구만 전송(스팸 방지)
    필요한 env:
      TELEGRAM_WEBHOOK_URL=...
      DISCORD_WEBHOOK_URL=...
    반환: 결과 meta(dict)
    """
    # promotions 파일에서 1줄 가져오기
    project_root = Path(__file__).resolve().parent
    promo_dir = project_root / "outputs" / product_id / "promotions"
    x_posts = promo_dir / "x_posts.txt"

    text = ""
    if x_posts.exists():
        try:
            lines = x_posts.read_text(encoding="utf-8", errors="ignore").splitlines()
            text = next((ln.strip() for ln in lines if ln.strip()), "")
        except Exception:
            text = ""

    if not text:
        text = f"[{product_id}] Promotions ready. (No text extracted)"

    results = {"product_id": product_id, "created_at": _utc_iso(), "sent": []}

    tg = os.getenv("TELEGRAM_WEBHOOK_URL", "").strip()
    dc = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

    # Telegram: payload 형식은 웹훅 구현에 따라 다르므로 가장 범용적인 {"text": "..."}를 사용
    if tg:
        ok = _safe_post_json(tg, {"text": text})
        results["sent"].append({"channel": "telegram_webhook", "ok": ok})

    # Discord: webhook은 {"content": "..."}가 표준
    if dc:
        ok = _safe_post_json(dc, {"content": text})
        results["sent"].append({"channel": "discord_webhook", "ok": ok})

    # 결과를 파일로 남김(운영 가시성)
    promo_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(promo_dir / "publish_results.json", results)
    return results
