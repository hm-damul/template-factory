# -*- coding: utf-8 -*-
"""
promotion_dispatcher.py

대시보드에서 입력한 "채널 키/웹훅" 설정을 기반으로,
제품별 promotions 산출물을 채널별 포맷으로 변환하고(페이로드 생성),
가능하면 안전하게(키/URL 존재 시에만) 발행을 시도합니다.

⚠️ 안전 기본값:
- Instagram/TikTok/YouTube는 각 플랫폼의 OAuth/검증이 복잡하고 계정 제재 리스크가 있어,
  본 프로젝트에서는 "웹훅 URL 기반" 또는 "파일 생성" 형태를 기본으로 제공합니다.
- WordPress는 REST API 기반 draft 발행을 지원합니다(토큰이 있으면).
- 아무 키/URL이 없으면: 발행 시도 없이, 채널별 payload 파일만 생성하고 ready_to_publish 상태를 남깁니다.

저장:
- data/promo_channels.json : 채널 설정(대시보드 폼으로 저장)
- outputs/<product_id>/promotions/channel_payloads.json : 채널별 payload 요약
- outputs/<product_id>/promotions/publish_results.json : 발행 시도 결과
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Tuple

import requests

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
CONFIG_PATH = DATA_DIR / "promo_channels.json"


def _utc_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _atomic_write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


def load_channel_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {
            "updated_at": None,
            "blog": {
                "mode": "none",
                "webhook_url": "",
                "wp_api_url": "",
                "wp_token": "",
            },
            "instagram": {"webhook_url": "", "enabled": False},
            "tiktok": {"webhook_url": "", "enabled": False},
            "youtube_shorts": {"webhook_url": "", "enabled": False},
            "dry_run": True,
        }
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {
            "updated_at": None,
            "blog": {
                "mode": "none",
                "webhook_url": "",
                "wp_api_url": "",
                "wp_token": "",
            },
            "instagram": {"webhook_url": "", "enabled": False},
            "tiktok": {"webhook_url": "", "enabled": False},
            "youtube_shorts": {"webhook_url": "", "enabled": False},
            "dry_run": True,
        }


def save_channel_config(cfg: Dict[str, Any]) -> None:
    cfg = dict(cfg)
    cfg["updated_at"] = _utc_iso()
    _atomic_write_json(CONFIG_PATH, cfg)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore").strip()
    except Exception:
        return ""


def _extract_primary_x_post(promotions_dir: Path) -> str:
    x_posts = promotions_dir / "x_posts.txt"
    text = _read_text(x_posts)
    if not text:
        return ""
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def _extract_newsletter(promotions_dir: Path) -> str:
    return _read_text(promotions_dir / "newsletter_email.txt")


def _extract_seo(promotions_dir: Path) -> str:
    return _read_text(promotions_dir / "seo.txt")


def _simple_markdown_to_html(md: str) -> str:
    # 아주 단순 변환(외부 라이브러리 없이)
    lines = md.splitlines()
    out = []
    for ln in lines:
        ln = ln.rstrip()
        if ln.startswith("# "):
            out.append(f"<h1>{ln[2:].strip()}</h1>")
        elif ln.startswith("## "):
            out.append(f"<h2>{ln[3:].strip()}</h2>")
        elif ln.startswith("- "):
            out.append(f"<li>{ln[2:].strip()}</li>")
        elif ln.strip() == "":
            out.append("<br/>")
        else:
            out.append(f"<p>{ln}</p>")
    html = "\n".join(out)
    # list wrapping (very naive)
    html = html.replace("</li>\n<li>", "</li><li>")
    if "<li>" in html:
        html = html.replace("<li>", "<ul><li>", 1)
        html = html[::-1].replace(">lu/<", ">lu/<" + "</ul>"[::-1], 1)[
            ::-1
        ]  # append closing </ul> once
    return html


def build_channel_payloads(product_id: str) -> Dict[str, Any]:
    """
    outputs/<product_id>/promotions/ 에서 채널별 발행 payload를 생성.
    """
    product_dir = PROJECT_ROOT / "outputs" / product_id
    promotions_dir = product_dir / "promotions"
    promotions_dir.mkdir(parents=True, exist_ok=True)

    title = ""
    manifest = product_dir / "manifest.json"
    if manifest.exists():
        try:
            m = json.loads(manifest.read_text(encoding="utf-8"))
            title = m.get("title", "") or m.get("product", {}).get("title", "")
        except Exception:
            title = ""

    # 기본 텍스트 구성 요소
    primary = _extract_primary_x_post(promotions_dir)
    newsletter = _extract_newsletter(promotions_dir)
    seo = _extract_seo(promotions_dir)

    # 유튜브/틱톡/인스타용 "스크립트"는 기존 파일을 기반으로 생성
    # (향후 고급화: product.pdf 내용을 요약해 훅+구조화)
    hook = primary or f"{title} — crypto-only checkout + instant delivery."
    ig_caption = hook + "\n\n" + "#crypto #payments #digitalproducts #privacy"
    tiktok_script = (
        "Hook (0-3s): " + hook + "\n\n"
        "Body (3-25s): Explain the core pain + 3 steps.\n"
        "CTA (25-30s): Buy with crypto → instant download.\n"
    )
    yt_shorts_script = (
        "Title: " + (title or "Crypto-first digital product") + "\n\n"
        "0-5s: Hook: " + hook + "\n"
        "5-45s: 3 bullet takeaways.\n"
        "45-60s: CTA: wallet payment → instant download.\n"
    )

    # 블로그용(마크다운/HTML) — promotions 폴더 내 파일을 활용
    blog_md = (
        f"# {title or product_id}\n\n"
        f"{hook}\n\n"
        "## What you get\n"
        "- product.pdf (guide/ebook)\n"
        "- bonus (checklists/prompts/scripts)\n"
        "- assets (icons)\n"
        "- promotions (marketing pack)\n\n"
        "## Why crypto-first buyers pay differently\n"
        "- Privacy-native\n"
        "- Global settlement\n"
        "- Lower friction vs card rails\n\n"
        "## How to use\n"
        "1) Buy with wallet\n2) Get instant download\n3) Apply the playbook\n\n"
        "## SEO\n"
        f"{seo}\n"
    )
    blog_html = _simple_markdown_to_html(blog_md)

    payloads = {
        "product_id": product_id,
        "created_at": _utc_iso(),
        "title": title,
        "blog": {"markdown": blog_md, "html": blog_html},
        "instagram": {"caption": ig_caption},
        "tiktok": {"script": tiktok_script},
        "youtube_shorts": {"script": yt_shorts_script},
        "source": {
            "primary_post": primary,
            "newsletter_email": newsletter[:4000],
            "seo": seo[:4000],
        },
    }

    # 파일로 저장
    (promotions_dir / "blog_post.md").write_text(blog_md + "\n", encoding="utf-8")
    (promotions_dir / "blog_post.html").write_text(blog_html + "\n", encoding="utf-8")
    (promotions_dir / "instagram_caption.txt").write_text(
        ig_caption + "\n", encoding="utf-8"
    )
    (promotions_dir / "tiktok_script.txt").write_text(
        tiktok_script + "\n", encoding="utf-8"
    )
    (promotions_dir / "youtube_shorts_script.txt").write_text(
        yt_shorts_script + "\n", encoding="utf-8"
    )
    _atomic_write_json(promotions_dir / "channel_payloads.json", payloads)
    return payloads


def _safe_post_json(url: str, payload: Dict[str, Any]) -> Tuple[bool, str]:
    try:
        r = requests.post(url, json=payload, timeout=15)
        ok = 200 <= int(r.status_code) < 300
        return ok, f"status={r.status_code}"
    except Exception as e:
        return False, f"error={e}"


def _publish_wordpress(
    wp_api_url: str, wp_token: str, title: str, html: str
) -> Tuple[bool, str]:
#     """
#     WordPress REST API draft 발행:
#       wp_api_url 예: https://example.com/wp-json/wp/v2/posts
#       Authorization: Bearer <token> (또는 Application Password를 Bearer로 쓰는 환경도 있음)
#     """
    try:
        headers = {
            "Authorization": f"Bearer {wp_token}",
            "Content-Type": "application/json",
        }
        payload = {"title": title or "New Post", "content": html, "status": "draft"}
        r = requests.post(wp_api_url, headers=headers, json=payload, timeout=20)
        ok = 200 <= int(r.status_code) < 300
        return ok, f"status={r.status_code}"
    except Exception as e:
        return False, f"error={e}"


def dispatch_publish(product_id: str) -> Dict[str, Any]:
    """
    설정에 따라 발행 시도.
    - 키/URL이 없으면: no-op(파일 생성만)
    """
    cfg = load_channel_config()
    payloads = build_channel_payloads(product_id)

    product_dir = PROJECT_ROOT / "outputs" / product_id
    promotions_dir = product_dir / "promotions"
    promotions_dir.mkdir(parents=True, exist_ok=True)

    results: Dict[str, Any] = {
        "product_id": product_id,
        "created_at": _utc_iso(),
        "dry_run": bool(cfg.get("dry_run", True)),
        "sent": [],
    }

    # Blog
    blog_cfg = cfg.get("blog", {}) if isinstance(cfg.get("blog", {}), dict) else {}
    blog_mode = str(blog_cfg.get("mode", "none") or "none").strip().lower()
    blog_webhook = str(blog_cfg.get("webhook_url", "") or "").strip()
    wp_api_url = str(blog_cfg.get("wp_api_url", "") or "").strip()
    wp_token = str(blog_cfg.get("wp_token", "") or "").strip()

    title = payloads.get("title") or product_id
    blog_html = payloads.get("blog", {}).get("html", "")

    if cfg.get("dry_run", True):
        results["sent"].append({"channel": "blog", "ok": True, "note": "dry_run"})
    else:
        if blog_mode == "wordpress" and wp_api_url and wp_token:
            ok, msg = _publish_wordpress(wp_api_url, wp_token, title, blog_html)
            results["sent"].append({"channel": "blog_wordpress", "ok": ok, "msg": msg})
        elif blog_mode == "webhook" and blog_webhook:
            ok, msg = _safe_post_json(
                blog_webhook,
                {"title": title, "html": blog_html, "product_id": product_id},
            )
            results["sent"].append({"channel": "blog_webhook", "ok": ok, "msg": msg})
        else:
            results["sent"].append({"channel": "blog", "ok": False, "msg": "no_config"})

    # Instagram / TikTok / YouTube Shorts
    for key, label, payload_key in [
        ("instagram", "instagram", "instagram"),
        ("tiktok", "tiktok", "tiktok"),
        ("youtube_shorts", "youtube_shorts", "youtube_shorts"),
    ]:
        ch = cfg.get(key, {}) if isinstance(cfg.get(key, {}), dict) else {}
        enabled = bool(ch.get("enabled", False))
        url = str(ch.get("webhook_url", "") or "").strip()

        if not enabled:
            results["sent"].append({"channel": label, "ok": True, "note": "disabled"})
            continue

        if cfg.get("dry_run", True):
            results["sent"].append({"channel": label, "ok": True, "note": "dry_run"})
            continue

        if url:
            ok, msg = _safe_post_json(
                url,
                {"product_id": product_id, "payload": payloads.get(payload_key, {})},
            )
            results["sent"].append(
                {"channel": f"{label}_webhook", "ok": ok, "msg": msg}
            )
        else:
            # 키/URL이 없으면 파일만 생성해둔다.
            results["sent"].append(
                {"channel": label, "ok": False, "msg": "no_webhook_url"}
            )

    _atomic_write_json(promotions_dir / "publish_results.json", results)
    return results
