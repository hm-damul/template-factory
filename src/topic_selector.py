from __future__ import annotations
import re
from typing import Dict, List

TREND_KEYWORDS = [
    "wallet checkout",
    "token-gated",
    "stablecoin",
    "on-chain",
    "AI agents",
    "automation",
    "webhook",
    "vercel static",
    "lead capture",
    "crypto",
    "EVM",
]

BUYER_INTENT = [
    "template",
    "framework",
    "system",
    "playbook",
    "landing page",
    "guide",
    "pack",
    "bundle",
]

VAGUE_WORDS = ["stuff", "things", "misc", "random", "various"]

def _score_topic(text: str) -> int:
    s = text.strip().lower()
    if not s:
        return 0
    score = 50
    ln = len(s)
    if 18 <= ln <= 90:
        score += 10
    if any(w in s for w in [" for ", " with ", " using ", " to ", " + "]):
        score += 8
    score += sum(5 for k in TREND_KEYWORDS if k in s)
    score += sum(6 for k in BUYER_INTENT if k in s)
    score -= sum(8 for k in VAGUE_WORDS if k in s)
    if re.search(r"\b(guide|system|framework|template|bundle)\b", s):
        score += 6
    return max(0, min(100, score))

def _candidates(base: str) -> List[Dict[str, str]]:
    b = (base or "").strip()
    seeds = [
        "Crypto Wallet Checkout + Token-Gated Delivery System for Digital Products",
        "Stablecoin Wallet Checkout Template with Token-Gated Downloads",
        "On-chain Lead Capture + Wallet Checkout Landing Page Template",
        "AI Agents + Webhook Automation Playbook for Token-Gated Sales",
        "EVM Wallet Checkout Framework: Vercel Static One-File Landing",
    ]
    if b:
        seeds.insert(0, b)
    out: List[Dict[str, str]] = []
    for t in seeds[:6]:
        headline = t
        sub = "Launch crypto-ready sales with wallet checkout and token-gated delivery."
        out.append(
            {
                "topic": t,
                "headline": headline,
                "subheadline": sub,
                "keywords": ", ".join(sorted(set(TREND_KEYWORDS + BUYER_INTENT))),
            }
        )
    return out

from .utils import get_logger

logger = get_logger(__name__)

def select_topic(base_topic: str = "") -> Dict[str, str]:
    # AI Web Research for Topic Ideas if auto/empty
    if not base_topic or base_topic.lower() in ["auto", "random"]:
        try:
            from .ai_web_researcher import web_researcher
            logger.info("Auto-selecting topic via Web Research...")
            # Search for highly specific trending niche products
            # Use a query that is known to return results
            trends = web_researcher.search("trending digital products 2025 profitable ideas")
            if trends:
                # Find the first relevant title that isn't a generic support page
                found_topic = ""
                for t in trends:
                    title_lower = t['title'].lower()
                    if "support.google" in t['link'] or "trends.google" in t['link']:
                        continue
                    if "github" in title_lower and "trending" in title_lower:
                        # GitHub trending is often code, not products to sell, but maybe okay for inspiration
                        pass
                    
                    found_topic = t['title']
                    break
                
                if not found_topic and trends:
                    found_topic = trends[0]['title']

                # Clean up title if it's too long or has site name
                found_topic = found_topic.split(" | ")[0].split(" - ")[0]
                base_topic = found_topic
                logger.info(f"Web Research suggested topic: {base_topic}")
        except Exception as e:
            logger.warning(f"Web topic selection failed: {e}")

    cands = _candidates(base_topic)
    ranked = sorted(cands, key=lambda x: _score_topic(x["topic"]), reverse=True)
    return ranked[0] if ranked else {"topic": base_topic, "headline": base_topic, "subheadline": ""}
