# -*- coding: utf-8 -*-
"""
premium_content_engine.py

목적:
- "요약 같은 얕은 글"이 아니라, 유료 전자책 수준의 깊이/구조/실무성을 가진 콘텐츠를
  외부 LLM 없이도 결정적으로 생성한다.
- product_id 기반 seed로 항상 동일한 결과를 재현한다.

핵심 아이디어:
- PREMIUM_BLUEPRINT(9개 섹션) 고정 구조
- 각 섹션은 3~6페이지 분량을 목표로: (1) 서브헤더 다수, (2) 불릿/번호 목록,
  (3) 숫자 예시(전환율/예산/타임라인), (4) 워크플로우, (5) 체크리스트, (6) 콜아웃(Expert Notes/Pro Tip)
- "가짜지만 현실적인" 케이스 스터디: 타겟/채널/수치/기간/Before vs After 포함
- 제품별 결정성(determinism): 동일 product_id => 동일 섹션/수치/예시/표

주의:
- 이 모듈은 "텍스트/구조 데이터"를 생성한다.
- PDF 레이아웃은 premium_pdf_builder.py가 담당한다.
"""

from __future__ import annotations

import hashlib
import random
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# -----------------------------
# Public Data Structures
# -----------------------------


@dataclass(frozen=True)
class Callout:
    """PDF/Markdown에서 박스 형태로 표현할 콜아웃."""

    kind: str  # "expert_note" | "pro_tip" | "warning"
    title: str
    body: str


@dataclass(frozen=True)
class Subsection:
    """섹션 내부의 소단락(서브헤더 단위)"""

    title: str
    paragraphs: List[str]
    bullets: List[str]
    numbered_steps: List[str]
    callouts: List[Callout]


@dataclass(frozen=True)
class Section:
    """프리미엄 제품의 대단락"""

    key: str
    title: str
    subsections: List[Subsection]


@dataclass(frozen=True)
class PremiumProduct:
    """프리미엄 제품 전체 구조"""

    product_id: str
    topic: str
    title: str
    subtitle: str
    audience: str
    price_band: str
    sections: List[Section]
    toc: List[Tuple[str, str]]  # (section_key, section_title)
    meta: Dict[str, Any]  # metrics, scenario params, etc.


# -----------------------------
# Deterministic helpers
# -----------------------------


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def seed_from_product_id(product_id: str) -> int:
    """product_id 기반 고정 seed."""
    return int(_sha256(product_id)[:8], 16)


def _rng_for(product_id: str, salt: str) -> random.Random:
    """product_id + salt로 독립 RNG를 만든다."""
    s = _sha256(f"{product_id}||{salt}")
    return random.Random(int(s[:8], 16))


def _slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "product"


# -----------------------------
# Premium Blueprint
# -----------------------------

BLUEPRINT: List[Tuple[str, str]] = [
    ("executive_overview", "1. Executive Overview"),
    ("strategic_foundation", "2. Strategic Foundation"),
    ("implementation_framework", "3. Implementation Framework"),
    ("case_study", "4. Case Study (Mandatory)"),
    ("tool_stack", "5. Tool Stack"),
    ("execution_checklist", "6. Execution Checklist"),
    ("advanced_strategies", "7. Advanced Strategies"),
    ("troubleshooting", "8. Troubleshooting"),
    ("roadmap", "9. Next Steps Roadmap (30/60/90)"),
]


# -----------------------------
# Domain libraries (no LLM, still rich)
# -----------------------------

TARGET_AUDIENCES = [
    "privacy-first crypto wallet users who want chargeback-free digital purchases",
    "solo merchants selling downloadable products to a global audience using stablecoins",
    "Web3 builders who need token-gated content + automated delivery after on-chain payment",
    "creators running anonymous sales funnels and requiring minimal personal data collection",
]

MARKET_REALITIES = [
    "Most buyers won't trust a new site unless the checkout is frictionless, the value is obvious, and delivery is instant.",
    "Crypto buyers have a low tolerance for vague claims. They want proof, process, and clear risk boundaries.",
    "The biggest bottleneck is not 'traffic' but a credible offer + repeatable conversion system.",
    "Chargeback-free payments are a huge advantage—but only if you can prevent refund friction and support overload.",
]

CORE_PRINCIPLES = [
    "Design for trust: transparency, predictable steps, explicit outcomes, and a no-surprises payment flow.",
    "Optimize for operational simplicity: fewer moving parts, deterministic builds, and clear incident playbooks.",
    "Treat content as a product: structure, examples, checklists, and implementable workflows beat opinions.",
    "Instrument everything: conversion, drop-offs, payment success rate, delivery success rate, and support tickets per 100 sales.",
]

COMMON_MISTAKES = [
    "Shipping 'a nice-looking PDF' with no execution system, templates, or measurable outcomes.",
    "Ignoring purchase friction (wallet UX, network fees, confirmation time) and blaming traffic.",
    "No gating logic: letting unpaid users access downloads via direct URLs.",
    "No support model: no FAQ, no troubleshooting, no refund/cancellation policy boundaries.",
    "Over-automating before you have a stable baseline and analytics instrumentation.",
]

TOOLS_LIBRARY = [
    (
        "Vercel",
        "Static + serverless deployment with global CDN; easy to ship landing + API endpoints together.",
    ),
    (
        "Flask",
        "Local preview/testing for development; keep production on serverless endpoints.",
    ),
    (
        "NOWPayments",
        "Crypto payment gateway supporting many coins; provides invoice and payment status APIs.",
    ),
    (
        "Cloudflare Turnstile",
        "Bot mitigation without heavy friction; protects pay/start endpoints.",
    ),
    (
        "Plausible/Umami",
        "Lightweight analytics; track funnel events without invasive tracking.",
    ),
    ("Sentry", "Error monitoring for API endpoints and client errors."),
    (
        "PostHog",
        "Product analytics; cohort analysis and event pipelines if you need more depth.",
    ),
]

CHANNELS = [
    ("X/Twitter", "fast iteration, hooks + credibility posts, short threads"),
    ("Reddit", "value-first breakdowns, case studies, avoid hard selling"),
    ("YouTube Shorts/TikTok", "quick demos, before/after, 'system' framing"),
    ("Email", "nurture sequence, narrative + proof, limited-time bundles"),
    ("SEO", "evergreen keywords, comparison pages, long-tail queries"),
]


# -----------------------------
# Metric/scenario synthesis (deterministic)
# -----------------------------


def _pick(rng: random.Random, items: List[str]) -> str:
    return items[rng.randrange(0, len(items))]


def _pct(rng: random.Random, lo: float, hi: float, step: float = 0.1) -> float:
    """예: 1.2% 같은 비율 생성"""
    n = int((hi - lo) / step)
    v = lo + rng.randrange(0, max(1, n + 1)) * step
    return round(v, 1)


def _usd(rng: random.Random, lo: int, hi: int, step: int = 5) -> int:
    n = int((hi - lo) / step)
    return lo + rng.randrange(0, max(1, n + 1)) * step


def _days(rng: random.Random, lo: int, hi: int) -> int:
    return rng.randrange(lo, hi + 1)


def synthesize_meta(product_id: str, topic: str) -> Dict[str, Any]:
    """제품 전체에서 공유할 메타(수치/시나리오 파라미터)."""
    rng = _rng_for(product_id, "meta")
    audience = _pick(rng, TARGET_AUDIENCES)

    # 현실적인 퍼널 수치(가짜이지만 plausible)
    lp_to_checkout = _pct(rng, 1.2, 4.8, 0.1)  # 방문 -> 결제시작
    checkout_to_paid = _pct(rng, 42.0, 78.0, 1.0)  # 결제시작 -> 결제완료
    paid_to_download = _pct(rng, 94.0, 99.5, 0.1)  # 결제완료 -> 다운로드 성공
    support_rate = _pct(rng, 1.0, 6.0, 0.1)  # 100건당 문의 비율

    # 예산/기간
    monthly_budget = _usd(rng, 80, 600, 20)
    timeline_days = _days(rng, 21, 45)

    # 가격대(지각 가치)
    price_band = _pick(rng, ["$29–$49", "$39–$59", "$49–$79"])

    # 코인/네트워크 예시
    coin = _pick(rng, ["USDT (TRC20)", "USDC (Polygon)", "ETH", "SOL", "BTC"])
    network_fee_usd = round(_pct(rng, 0.2, 5.0, 0.1), 1)

    # 케이스 스터디용 수치
    baseline_visits = _usd(rng, 800, 6000, 100)
    baseline_conv = _pct(rng, 0.8, 2.2, 0.1)
    improved_conv = round(min(6.5, baseline_conv + _pct(rng, 0.6, 2.4, 0.1)), 1)
    aov = _usd(rng, 29, 79, 5)
    period_days = _days(rng, 14, 30)

    return {
        "topic": topic,
        "audience": audience,
        "price_band": price_band,
        "funnel": {
            "lp_to_checkout_pct": lp_to_checkout,
            "checkout_to_paid_pct": checkout_to_paid,
            "paid_to_download_pct": paid_to_download,
            "support_per_100_sales_pct": support_rate,
        },
        "ops": {
            "monthly_budget_usd": monthly_budget,
            "timeline_days": timeline_days,
            "primary_coin": coin,
            "avg_network_fee_usd": network_fee_usd,
        },
        "case": {
            "baseline_visits": baseline_visits,
            "baseline_conv_pct": baseline_conv,
            "improved_conv_pct": improved_conv,
            "aov_usd": aov,
            "period_days": period_days,
        },
    }


# -----------------------------
# Section generators
# -----------------------------


def _make_subsection(
    title: str,
    paragraphs: List[str],
    bullets: Optional[List[str]] = None,
    numbered_steps: Optional[List[str]] = None,
    callouts: Optional[List[Callout]] = None,
) -> Subsection:
    return Subsection(
        title=title,
        paragraphs=paragraphs,
        bullets=bullets or [],
        numbered_steps=numbered_steps or [],
        callouts=callouts or [],
    )


def _callout(kind: str, title: str, body: str) -> Callout:
    return Callout(kind=kind, title=title, body=body)


def _expert_note(rng: random.Random, meta: Dict[str, Any], hint: str) -> Callout:
    notes = [
        f"Do not chase perfection. Ship a stable baseline in ≤{meta['ops']['timeline_days']} days, then iterate via metrics.",
        "If the payment provider webhook is unreliable, treat polling as the source of truth but add backoff + idempotency.",
        "Your highest ROI is usually on-page clarity (offer, outcomes, proof) before spending more on traffic.",
        f"Support load is a hidden tax. Keep it below ~{meta['funnel']['support_per_100_sales_pct']}% per 100 sales using FAQ + troubleshooting.",
    ]
    return _callout("expert_note", f"Expert Note — {hint}", _pick(rng, notes))


def _pro_tip(rng: random.Random, meta: Dict[str, Any], hint: str) -> Callout:
    tips = [
        f"Optimize for time-to-value: aim for 'paid → download' success rate ≥ {meta['funnel']['paid_to_download_pct']}%.",
        "Turn the first 200 words into a sales page: define outcome, time saved, and the exact system inside.",
        "Use 2-step pricing: base product + bundle bonus. It increases perceived value without extra code.",
        f"Treat network fees as UX. Display estimated fee (~${meta['ops']['avg_network_fee_usd']}) and suggested coin to reduce abandonment.",
    ]
    return _callout("pro_tip", f"Pro Tip — {hint}", _pick(rng, tips))


def _generate_executive_overview(product_id: str, meta: Dict[str, Any]) -> Section:
    rng = _rng_for(product_id, "executive_overview")
    topic = meta["topic"]
    audience = meta["audience"]
    funnel = meta["funnel"]
    ops = meta["ops"]

    s1 = _make_subsection(
        "Problem Definition",
        paragraphs=[
            f"This product is a practical implementation guide for: **{topic}**.",
            "Many crypto digital products fail because the deliverable is vague and the execution system is missing. "
            "Buyers do not pay for 'information'; they pay for a repeatable result.",
            f"Target audience: {audience}.",
        ],
        bullets=[
            "Shallow content → low perceived value → price ceiling collapses.",
            "No measurable outcomes → no trust → low conversion.",
            "No operational workflow → support overload → churn and refunds.",
        ],
        callouts=[_expert_note(rng, meta, "Scope")],
    )

    s2 = _make_subsection(
        "Market Reality",
        paragraphs=[
            _pick(rng, MARKET_REALITIES),
            "Crypto checkout adds unique friction: wallet UX, confirmation time, network fees, and coin selection. "
            "A premium product must proactively neutralize this friction.",
        ],
        bullets=[
            f"Typical landing → checkout start: ~{funnel['lp_to_checkout_pct']}%",
            f"Typical checkout start → paid: ~{funnel['checkout_to_paid_pct']}%",
            f"Paid → successful download: ~{funnel['paid_to_download_pct']}%",
            f"Support tickets per 100 sales: ~{funnel['support_per_100_sales_pct']}%",
            f"Baseline build timeline target: {ops['timeline_days']} days",
        ],
        callouts=[_pro_tip(rng, meta, "Funnel metrics")],
    )

    s3 = _make_subsection(
        "Why This Matters Now",
        paragraphs=[
            "Payments are shifting: stablecoins are increasingly used for cross-border purchases, "
            "and buyers expect instant digital delivery. You can turn this into a defensible advantage.",
            "The point of this guide is not hype; it is an operational playbook that you can run repeatedly.",
        ],
        bullets=[
            "A premium offer is a *system*, not a PDF.",
            "Deterministic builds reduce ops burden and prevent 'it worked yesterday' incidents.",
            "Instrumented funnels enable compounding improvements over time.",
        ],
    )

    return Section(
        key="executive_overview",
        title="Executive Overview",
        subsections=[s1, s2, s3],
    )


def _generate_strategic_foundation(product_id: str, meta: Dict[str, Any]) -> Section:
    rng = _rng_for(product_id, "strategic_foundation")

    s1 = _make_subsection(
        "Core Principles",
        paragraphs=[
            "A premium digital product behaves like a small software product: it has deliverables, versioning, QA, and support boundaries.",
            "Your strategy should optimize for credibility and repeatability before scaling traffic.",
        ],
        bullets=CORE_PRINCIPLES,
        callouts=[_expert_note(rng, meta, "Principles")],
    )

    s2 = _make_subsection(
        "Realistic Expectations",
        paragraphs=[
            "The goal is not 'viral'. The goal is a predictable machine with tight feedback loops.",
            "Use a 3-iteration model: baseline → instrument → optimize. Stop adding features until your baseline converts.",
        ],
        bullets=[
            "Iteration 1: build + ship + measure (conversion + payment success + delivery success).",
            "Iteration 2: reduce friction (copy, FAQ, payment options, fee guidance).",
            "Iteration 3: add leverage (automation, promo distribution, upsell bundles).",
        ],
        callouts=[_pro_tip(rng, meta, "Iteration model")],
    )

    s3 = _make_subsection(
        "Mistakes to Avoid",
        paragraphs=[
            "Most failures are process failures. Avoid these common traps that crush perceived value or create operational debt.",
        ],
        bullets=COMMON_MISTAKES,
        callouts=[
            _callout(
                "warning",
                "Warning — Value Trap",
                "If your deliverable can be summarized into 10 bullet points, buyers will treat it as 'free blog content'.",
            )
        ],
    )

    return Section(
        key="strategic_foundation",
        title="Strategic Foundation",
        subsections=[s1, s2, s3],
    )


def _implementation_steps(product_id: str, meta: Dict[str, Any]) -> List[Subsection]:
    rng = _rng_for(product_id, "implementation_framework")
    funnel = meta["funnel"]
    ops = meta["ops"]

    steps = [
        (
            "Define the Offer (Outcome + Proof + Boundaries)",
            "Turn the topic into a concrete outcome statement. Buyers should understand value in 10 seconds.",
            [
                "Write a one-sentence outcome: 'In X days, you will achieve Y without Z.'",
                "List 3 proof points: case metric, template count, system diagram.",
                "Define boundaries: what this product does NOT cover (prevents refunds/support).",
            ],
            f"Example: Improve LP→Checkout from {funnel['lp_to_checkout_pct']}% to ~{round(funnel['lp_to_checkout_pct']+1.0,1)}% by rewriting above-the-fold copy and adding proof blocks.",
        ),
        (
            "Instrument the Funnel",
            "You can't improve what you can't see. Instrument events from landing to delivery.",
            [
                "Track: page_view, click_buy, pay_start, pay_success, download_success, support_click.",
                "Log server-side: order_id, product_id, amount, currency, status transitions.",
                "Set SLO targets (e.g., download success ≥ 98%).",
            ],
            "Example: A single dashboard showing pay_start→paid conversion reveals whether fees/coin choice is causing drop-off.",
        ),
        (
            "Harden Payment + Delivery Gating",
            "Crypto payments are final. Your delivery must be accurate, idempotent, and strongly gated.",
            [
                "Generate a unique order_id per attempt; store status with timestamps.",
                "Only allow download after 'paid' is confirmed server-side.",
                "Make endpoints idempotent: repeated calls should not create duplicated invoices.",
            ],
            f"Example: With paid→download success at {funnel['paid_to_download_pct']}%, your biggest risk is accidental free downloads. Add signed URLs or server-side file streaming.",
        ),
        (
            "Create a Support-Minimizing Product Package",
            "Premium products include assets that reduce confusion: checklists, worksheets, prompt packs, scripts.",
            [
                "Add an execution checklist and milestone checklist.",
                "Add troubleshooting matrix: symptom → cause → fix.",
                "Add a 30/60/90 roadmap so buyers know what to do next.",
            ],
            f"Example: Keep support under {funnel['support_per_100_sales_pct']}% per 100 sales by answering 10 common questions proactively.",
        ),
        (
            "Promotion System (Repeatable, Not Random)",
            "Your promo engine should produce channel-specific assets with consistent hooks and proof.",
            [
                "Define 3 message angles: privacy, profit, automation.",
                "Generate variations per channel; include a CTA to the landing page.",
                "Schedule distribution (batch posting) and record performance.",
            ],
            f"Example: Spend ${ops['monthly_budget_usd']}/mo on experiments and require a 'learned insight' after each 7-day cycle.",
        ),
    ]

    subs: List[Subsection] = []
    for idx, (title, why, actions, example) in enumerate(steps, start=1):
        subs.append(
            _make_subsection(
                f"Step {idx}: {title}",
                paragraphs=[
                    f"**Goal:** {title}",
                    f"**Why it matters:** {why}",
                    "Below are the exact actions to execute.",
                    f"**Example scenario:** {example}",
                ],
                numbered_steps=[f"{i+1}. {a}" for i, a in enumerate(actions)],
                callouts=[
                    (
                        _pro_tip(rng, meta, f"Step {idx}")
                        if idx % 2 == 0
                        else _expert_note(rng, meta, f"Step {idx}")
                    )
                ],
            )
        )
    return subs


def _generate_implementation_framework(
    product_id: str, meta: Dict[str, Any]
) -> Section:
    rng = _rng_for(product_id, "implementation_framework_intro")

    intro = _make_subsection(
        "System Overview",
        paragraphs=[
            "This section is the core of the product: a step-by-step implementation system you can execute end-to-end.",
            "Treat it like a runbook. Complete the steps in order before attempting advanced optimizations.",
        ],
        bullets=[
            "Output artifacts: premium PDF, diagrams, bonus package, promotions, deploy bundle.",
            "SLOs: payment success, delivery success, low support load.",
            "Deterministic builds: identical product_id produces identical artifacts for reproducibility.",
        ],
        callouts=[_expert_note(rng, meta, "Runbook mindset")],
    )

    subs = [intro] + _implementation_steps(product_id, meta)
    return Section(
        key="implementation_framework",
        title="Implementation Framework",
        subsections=subs,
    )


def _generate_case_study(product_id: str, meta: Dict[str, Any]) -> Section:
    rng = _rng_for(product_id, "case_study")
    case = meta["case"]
    ops = meta["ops"]

    baseline_paid = int(case["baseline_visits"] * (case["baseline_conv_pct"] / 100.0))
    improved_paid = int(case["baseline_visits"] * (case["improved_conv_pct"] / 100.0))
    baseline_rev = baseline_paid * case["aov_usd"]
    improved_rev = improved_paid * case["aov_usd"]

    persona = _pick(
        rng,
        [
            "a solo creator selling an 'Ops-ready crypto checkout template'",
            "a micro-agency packaging a 'global settlement toolkit for merchants'",
            "a Web3 builder selling token-gated onboarding materials",
        ],
    )

    s1 = _make_subsection(
        "Scenario Setup",
        paragraphs=[
            f"We use a fictional but realistic scenario: {persona}.",
            f"Time window: {case['period_days']} days. Monthly budget: ${ops['monthly_budget_usd']}. Primary coin: {ops['primary_coin']}.",
            "The product itself is premium-structured: it includes diagrams, checklists, prompt packs, and a 30/60/90 roadmap.",
        ],
        bullets=[
            f"Traffic: {case['baseline_visits']} visits",
            f"AOV: ${case['aov_usd']}",
            "Payment model: pay → confirm → gated download",
            "Instrumentation: event tracking + server-side order log",
        ],
        callouts=[_pro_tip(rng, meta, "Case setup")],
    )

    s2 = _make_subsection(
        "Before vs After (Metrics)",
        paragraphs=[
            "We compare baseline vs improved after applying the implementation steps (offer clarity, instrumentation, gating, and support reduction).",
            "The goal is not 'a miracle' but a plausible uplift that a disciplined operator can reproduce.",
        ],
        bullets=[
            f"Baseline conversion: {case['baseline_conv_pct']}% → {baseline_paid} paid purchases",
            f"Improved conversion: {case['improved_conv_pct']}% → {improved_paid} paid purchases",
            f"Revenue: ${baseline_rev} → ${improved_rev}",
            f"Lift: +{(improved_rev - baseline_rev)} (${(improved_rev - baseline_rev) / max(1, baseline_rev) * 100:.0f}% relative)",
        ],
        callouts=[_expert_note(rng, meta, "Metrics realism")],
    )

    s3 = _make_subsection(
        "Timeline & Actions",
        paragraphs=[
            "Here is a realistic action timeline showing what was changed and when.",
        ],
        numbered_steps=[
            "Day 1–3: Rewrite above-the-fold copy; add proof blocks; publish v1 landing.",
            "Day 4–7: Add event instrumentation; collect baseline funnel metrics.",
            "Day 8–12: Improve checkout UX (coin guidance, fee visibility, retry messaging).",
            "Day 13–18: Add troubleshooting + FAQ; reduce support load.",
            "Day 19–30: Add promo batch distribution; iterate based on best-performing hooks.",
        ],
        callouts=[
            _callout(
                "pro_tip",
                "Pro Tip — Validation",
                "A/B test ONE major change per 7 days to avoid confusing cause and effect.",
            )
        ],
    )

    s4 = _make_subsection(
        "Lessons Learned",
        paragraphs=[
            "This case study highlights the 'premium product loop': ship a concrete system, instrument it, and iterate with discipline.",
        ],
        bullets=[
            "Clarity beats complexity: improving the first screen often yields the fastest uplift.",
            "Gating correctness prevents revenue leakage and support nightmares.",
            "Bonus materials are not fluff; they reduce buyer uncertainty and increase perceived value.",
            "Roadmaps reduce 'what now?' confusion and reduce refund requests.",
        ],
    )

    return Section(
        key="case_study",
        title="Case Study (Mandatory)",
        subsections=[s1, s2, s3, s4],
    )


def _generate_tool_stack(product_id: str, meta: Dict[str, Any]) -> Section:
    rng = _rng_for(product_id, "tool_stack")

    chosen = TOOLS_LIBRARY[:]  # keep deterministic order, but include subset emphasis
    # deterministic rotate for variety
    rot = _rng_for(product_id, "tool_rotate").randrange(0, len(chosen))
    chosen = chosen[rot:] + chosen[:rot]

    bullets = []
    for name, why in chosen[:6]:
        bullets.append(f"**{name}** — {why}")

    s1 = _make_subsection(
        "Recommended Tools",
        paragraphs=[
            "This product is designed to be implementable with minimal dependencies. "
            "However, a premium setup uses a small tool stack for reliability and growth.",
        ],
        bullets=bullets,
        callouts=[_expert_note(rng, meta, "Tool selection")],
    )

    s2 = _make_subsection(
        "How They Integrate (System View)",
        paragraphs=[
            "Think in layers: landing → payment API → order store → gated download. "
            "Instrumentation and monitoring sit alongside these layers.",
        ],
        bullets=[
            "Landing (static): includes CTA, proof, pricing, FAQs, and payment start button.",
            "Payment (serverless): creates invoice and checks status, idempotent per order_id.",
            "Order store: append-only log or JSON store; supports audit and reconciliation.",
            "Delivery: server-side streaming of package.zip after paid.",
            "Analytics/monitoring: events + error monitoring + basic SLO dashboard.",
        ],
        callouts=[_pro_tip(rng, meta, "Integration")],
    )

    return Section(
        key="tool_stack",
        title="Tool Stack",
        subsections=[s1, s2],
    )


def _generate_execution_checklist(product_id: str, meta: Dict[str, Any]) -> Section:
    rng = _rng_for(product_id, "execution_checklist")
    ops = meta["ops"]

    s1 = _make_subsection(
        "Action Checklist (Ship v1)",
        paragraphs=[
            "Use this checklist to ship a baseline that you can sell today.",
            f"Target timeline: {ops['timeline_days']} days.",
        ],
        bullets=[
            "Define offer: outcome + proof + boundaries",
            "Write landing sections: hero, benefits, proof, pricing, FAQ, CTA",
            "Implement pay/start, pay/check, pay/download (server-side gating)",
            "Generate premium PDF + diagrams + bonus materials + promotions",
            "Deploy bundle and run smoke test",
        ],
        callouts=[_pro_tip(rng, meta, "Baseline shipping")],
    )

    s2 = _make_subsection(
        "Milestone Checklist (Operational)",
        paragraphs=[
            "After shipping v1, use milestones to avoid random work and maintain compounding improvements.",
        ],
        bullets=[
            "Milestone A: Funnel instrumented + baseline metrics collected",
            "Milestone B: Payment success rate stabilized (retry handling, fee guidance)",
            "Milestone C: Support load bounded (FAQ + troubleshooting + policies)",
            "Milestone D: Promo engine producing consistent assets and tracking performance",
            "Milestone E: 30/60/90 roadmap executed with weekly review cadence",
        ],
        callouts=[_expert_note(rng, meta, "Milestones")],
    )

    return Section(
        key="execution_checklist",
        title="Execution Checklist",
        subsections=[s1, s2],
    )


def _generate_advanced_strategies(product_id: str, meta: Dict[str, Any]) -> Section:
    rng = _rng_for(product_id, "advanced_strategies")
    ops = meta["ops"]

    s1 = _make_subsection(
        "Scaling (Traffic + Offer)",
        paragraphs=[
            "Scale only after baseline stability. Then scale in two dimensions: traffic acquisition and offer depth.",
        ],
        bullets=[
            "Traffic: double down on the channel with the best pay_start → paid rate.",
            "Offer: add bundle bonuses (scripts, prompt packs, templates) to raise perceived value.",
            "Pricing: test $29 → $49 if support load and refund pressure are controlled.",
        ],
        callouts=[_pro_tip(rng, meta, "Scaling discipline")],
    )

    s2 = _make_subsection(
        "Optimization (Conversion)",
        paragraphs=[
            "Conversion is a system: copy, proof, UX, fees, and trust cues all interact.",
            "Run controlled experiments with a single primary metric.",
        ],
        numbered_steps=[
            "Pick ONE metric (e.g., LP→Checkout).",
            "Generate 2 variations of hero section with different message angles.",
            "Run for 7 days or 200 visits (whichever comes later).",
            "Keep winner, document learning, then iterate next element.",
        ],
        callouts=[_expert_note(rng, meta, "Experiment design")],
    )

    s3 = _make_subsection(
        "Automation (Ops)",
        paragraphs=[
            "Once baseline is stable, automation compounds: scheduled promos, auto-regeneration for new topics, and automated QA.",
        ],
        bullets=[
            f"Budget rule: allocate ${ops['monthly_budget_usd']} / month for experiments and keep a written log of outcomes.",
            "Add nightly health checks: pay/start latency, pay/check error rate, download success.",
            "Auto-create new products only when QC score passes threshold.",
        ],
        callouts=[_pro_tip(rng, meta, "Automation")],
    )

    return Section(
        key="advanced_strategies",
        title="Advanced Strategies",
        subsections=[s1, s2, s3],
    )


def _generate_troubleshooting(product_id: str, meta: Dict[str, Any]) -> Section:
    rng = _rng_for(product_id, "troubleshooting")
    ops = meta["ops"]

    rows = [
        (
            "Users click Buy but no invoice appears",
            "pay/start failing or blocked",
            "Check server logs, Turnstile/bot rules, NOWPayments key, network timeouts",
        ),
        (
            "Invoice created but payment never completes",
            "coin/network mismatch or fees too high",
            f"Suggest {ops['primary_coin']}, show estimated fee (~${ops['avg_network_fee_usd']}), add retry guidance",
        ),
        (
            "Paid but download fails",
            "download endpoint gating or file path issue",
            "Verify server-side status check, stream package.zip, ensure file exists in bundle",
        ),
        (
            "Too many support emails",
            "missing FAQ, unclear boundaries",
            "Add troubleshooting matrix, explicit scope, and a 30/60/90 roadmap",
        ),
        (
            "Promotion posts get no traction",
            "weak hooks, no proof",
            "Use case metrics, show diagram, post before/after, focus on one channel and iterate",
        ),
    ]

    s1 = _make_subsection(
        "Common Failures → Fixes",
        paragraphs=[
            "Use this matrix to diagnose failures quickly. Premium operations mean fast recovery and minimal chaos.",
        ],
        bullets=[
            "Rule: every failure must map to a measurable metric and a remediation action.",
            "Rule: add logging before adding features.",
        ],
        callouts=[_expert_note(rng, meta, "Incident handling")],
    )

    # Represent the matrix as bullet blocks; PDF builder may render as table
    matrix_bullets = []
    for sym, cause, fix in rows:
        matrix_bullets.append(
            f"**Symptom:** {sym}\n- Likely cause: {cause}\n- Fix: {fix}"
        )
    s2 = _make_subsection(
        "Troubleshooting Matrix",
        paragraphs=[
            "Copy/paste-friendly format (useful for support macros).",
        ],
        bullets=matrix_bullets,
        callouts=[_pro_tip(rng, meta, "Support macros")],
    )

    # --- Structured troubleshooting matrix table for PDF ---
    meta.setdefault("tables", {})
    meta["tables"]["troubleshooting_matrix"] = {
        "headers": ["Symptom", "Likely cause", "Fix (exact actions)"],
        "rows": [
            [
                "Payment stuck pending",
                "Confirmations / network congestion",
                "Show ETA + confirmations required; advise checking invoice status; retry check in 2–5 minutes.",
            ],
            [
                "Wrong network paid",
                "User sent on unsupported chain",
                "Add guardrails: show supported chains; provide refund/credit policy; request tx hash; manual review.",
            ],
            [
                "Paid but cannot download",
                "Expired/invalid token or order not updated",
                "Re-issue signed token; refresh status; verify order state in store; mark delivered after success.",
            ],
            [
                "Invoice amount mismatch",
                "User underpaid due to fee/price drift",
                "Define exact tolerance; instruct to top-up; auto-detect partial payments if provider supports.",
            ],
        ],
        "note": "Keep this table visible in the PDF and reuse for support macros.",
    }

    return Section(
        key="troubleshooting",
        title="Troubleshooting",
        subsections=[s1, s2],
    )


def _generate_roadmap(product_id: str, meta: Dict[str, Any]) -> Section:
    rng = _rng_for(product_id, "roadmap")

    s1 = _make_subsection(
        "30 Days — Baseline + Instrumentation",
        paragraphs=[
            "Goal: ship v1, instrument funnel, and establish operational stability.",
        ],
        numbered_steps=[
            "Ship premium product package for one topic; deploy and smoke test.",
            "Add event tracking and server-side order logs; compute baseline funnel metrics.",
            "Write FAQ + troubleshooting; reduce support load and refund pressure.",
        ],
        callouts=[_expert_note(rng, meta, "Week 1-4")],
    )

    s2 = _make_subsection(
        "60 Days — Optimization + Bundling",
        paragraphs=[
            "Goal: raise perceived value and conversion via controlled experiments.",
        ],
        numbered_steps=[
            "Run 4 weekly experiments (copy, proof, coin guidance, checkout UX).",
            "Introduce bundle bonuses; test price tiers and measure impact on support.",
            "Stabilize automation: scheduled promo dispatch + QC gating.",
        ],
        callouts=[_pro_tip(rng, meta, "Week 5-8")],
    )

    s3 = _make_subsection(
        "90 Days — Scale + Portfolio Expansion",
        paragraphs=[
            "Goal: scale a proven system and expand to multiple products without quality decay.",
        ],
        numbered_steps=[
            "Add 3–5 adjacent products using the same premium blueprint (topic variations).",
            "Systematize reporting: weekly revenue, conversion, support load, incident count.",
            "Automate regeneration only when QC score passes; keep 'premium' bar enforced.",
        ],
        callouts=[_expert_note(rng, meta, "Week 9-12")],
    )

    return Section(
        key="roadmap",
        title="Next Steps Roadmap",
        subsections=[s1, s2, s3],
    )


SECTION_GENERATORS = {
    "executive_overview": _generate_executive_overview,
    "strategic_foundation": _generate_strategic_foundation,
    "implementation_framework": _generate_implementation_framework,
    "case_study": _generate_case_study,
    "tool_stack": _generate_tool_stack,
    "execution_checklist": _generate_execution_checklist,
    "advanced_strategies": _generate_advanced_strategies,
    "troubleshooting": _generate_troubleshooting,
    "roadmap": _generate_roadmap,
}


# -----------------------------
# Public API
# -----------------------------


def generate_premium_product(product_id: str, topic: str) -> PremiumProduct:
    """
    PREMIUM 제품을 생성한다.

    반환:
      PremiumProduct 구조(섹션/콜아웃/메타).
    """
    meta = synthesize_meta(product_id=product_id, topic=topic)

    rng = _rng_for(product_id, "title")
    title = topic.strip() or "Premium Crypto Digital Product"
    subtitle = _pick(
        rng,
        [
            "A premium, ops-ready playbook with diagrams, checklists, and realistic metrics",
            "A practical system: payment → gating → delivery → promotion (with QA loops)",
            "A professional implementation guide designed for $29–$79 perceived value",
        ],
    )

    sections: List[Section] = []
    for key, _label in BLUEPRINT:
        gen = SECTION_GENERATORS[key]
        sections.append(gen(product_id, meta))

    toc = [(s.key, s.title) for s in sections]

    return PremiumProduct(
        product_id=product_id,
        topic=topic,
        title=title,
        subtitle=subtitle,
        audience=meta["audience"],
        price_band=meta["price_band"],
        sections=sections,
        toc=toc,
        meta=meta,
    )


def to_markdown(prod: PremiumProduct) -> str:
    """
    PremiumProduct를 markdown으로 직렬화한다.
    - PDF 외에도 buyer-friendly 소스 제공/디버깅용.
    """
    out: List[str] = []
    out.append(f"# {prod.title}")
    out.append("")
    out.append(f"**product_id:** {prod.product_id}")
    out.append(f"**topic:** {prod.topic}")
    out.append(f"**audience:** {prod.audience}")
    out.append(f"**perceived value band:** {prod.price_band}")
    out.append("")
    out.append("---")
    out.append("")
    out.append("## Table of Contents")
    for i, (_, title) in enumerate(prod.toc, start=1):
        out.append(f"{i}. {title}")
    out.append("")
    out.append("---")
    out.append("")

    for sec in prod.sections:
        out.append(f"## {sec.title}")
        out.append("")
        for sub in sec.subsections:
            out.append(f"### {sub.title}")
            out.append("")
            for p in sub.paragraphs:
                out.append(p)
                out.append("")
            if sub.bullets:
                for b in sub.bullets:
                    # multi-line bullets allowed
                    blines = b.splitlines()
                    out.append(f"- {blines[0]}")
                    for extra in blines[1:]:
                        out.append(f"  {extra}")
                out.append("")
            if sub.numbered_steps:
                for step in sub.numbered_steps:
                    out.append(step)
                out.append("")
            for c in sub.callouts:
                label = {
                    "expert_note": "Expert Note",
                    "pro_tip": "Pro Tip",
                    "warning": "Warning",
                }.get(c.kind, c.kind)
                out.append(f"> **{label}: {c.title}**")
                out.append(f"> {c.body}")
                out.append("")
        out.append("")

    return "\n".join(out)
