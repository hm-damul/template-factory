# -*- coding: utf-8 -*-
"""
premium_bonus_generator.py

목적:
- 보너스 자료를 "텍스트 한 장"이 아니라, 실무에 바로 쓰는 고품질 패키지로 생성한다.

생성물(예):
outputs/<product_id>/bonus/
- execution_checklist.md         : 실행 체크리스트(액션/마일스톤)
- prompt_pack.md                 : 카테고리별 프롬프트 팩(콘텐츠/세일즈/분석/지원)
- scripts/
    - outreach_email_templates.md
    - support_macros.md
    - promo_scripts_shortform.md
- worksheets/
    - 30_60_90_plan.csv           : 계획 워크시트(스프레드시트로 열기 가능)
    - funnel_metrics_template.csv : 퍼널 기록 템플릿
- README.md                      : 보너스 사용법

주의:
- 외부 LLM 없이도 사용할 수 있는 형태로 "빈칸 채우기" 템플릿 중심.
- product_id 기반 결정적(내용은 topic/meta에 따라 변형).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from premium_content_engine import PremiumProduct


@dataclass(frozen=True)
class BonusBuildResult:
    ok: bool
    errors: List[str]
    files: List[Path]


def _safe_mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def build_bonus_package(bonus_dir: Path, product: PremiumProduct) -> BonusBuildResult:
    bonus_dir.mkdir(parents=True, exist_ok=True)

    files: List[Path] = []
    errors: List[str] = []

    meta = product.meta
    funnel = meta["funnel"]
    ops = meta["ops"]
    case = meta["case"]

    try:
        readme = bonus_dir / "README.md"
        readme.write_text(
            f"""# Bonus Package — {product.title}

product_id: {product.product_id}
topic: {product.topic}

This folder contains *editable* assets designed to reduce buyer confusion and increase execution success.

## What's inside
1) execution_checklist.md
2) prompt_pack.md
3) scripts/ (email templates, support macros, short-form promo scripts)
4) worksheets/ (CSV files you can open in Excel/Google Sheets)

## How to use
- Start with execution_checklist.md
- Copy/paste templates into your own tools (email, docs, social scheduling)
- Track metrics weekly using worksheets/funnel_metrics_template.csv
""",
            encoding="utf-8",
        )
        files.append(readme)
    except Exception as e:  # noqa: BLE001
        errors.append(f"README.md: {type(e).__name__}: {e}")

    # 1) Execution checklist
    try:
        p = bonus_dir / "execution_checklist.md"
        p.write_text(
            f"""# Execution Checklist (Premium)

## A) Ship v1 (Day 1–{ops['timeline_days']})
- [ ] Define the offer outcome in 1 sentence
- [ ] Add proof blocks (diagram + case metric + asset count)
- [ ] Implement payment start/check/download with server-side gating
- [ ] Generate premium PDF + diagrams + bonus package + promotions
- [ ] Deploy bundle and run smoke test

## B) Instrumentation (Week 1–2)
- [ ] Track events: page_view, click_buy, pay_start, pay_success, download_success, support_click
- [ ] Record server-side: order_id, product_id, amount, currency, status timestamps
- [ ] Baseline targets:
  - LP→Checkout: ~{funnel['lp_to_checkout_pct']}%
  - Checkout→Paid: ~{funnel['checkout_to_paid_pct']}%
  - Paid→Download: ≥{funnel['paid_to_download_pct']}%

## C) Support Boundaries (Week 2–3)
- [ ] Create FAQ and troubleshooting macros
- [ ] Define scope boundaries and refund policy
- [ ] Target support load: ≤{funnel['support_per_100_sales_pct']}% per 100 sales

## D) Weekly Review (ongoing)
- [ ] Review funnel metrics
- [ ] Choose ONE experiment
- [ ] Ship change, measure impact, document learning
""",
            encoding="utf-8",
        )
        files.append(p)
    except Exception as e:  # noqa: BLE001
        errors.append(f"execution_checklist.md: {type(e).__name__}: {e}")

    # 2) Prompt pack (category-based)
    try:
        p = bonus_dir / "prompt_pack.md"
        p.write_text(
            f"""# Prompt Pack (Category-based)

> Use these prompts later if you attach an LLM. They are structured to produce premium-quality outputs.

## 1) Offer & Positioning
- "Rewrite the hero section for '{product.topic}' targeting {product.audience}. Include: outcome, proof, boundaries, CTA."
- "Generate 5 value propositions with measurable outcomes and time-to-value framing."

## 2) Case Study Generator
- "Create a realistic case study for '{product.topic}'. Use metrics and a 14–30 day timeline. Include Before vs After table."

## 3) Troubleshooting & Support
- "List 15 buyer questions for '{product.topic}'. Provide crisp answers and link each to a product section."
- "Generate support macros: payment pending, wrong network, fee confusion, download issues."

## 4) Promotions (Channel-specific)
- "Create 10 X posts with hooks (privacy/profit/automation). Each includes one metric and one CTA."
- "Create 5 short-form scripts (30–45s) showing before/after with a single takeaway."

## 5) Analytics & Optimization
- "Given funnel metrics (LP→Checkout {funnel['lp_to_checkout_pct']}%, Checkout→Paid {funnel['checkout_to_paid_pct']}%), propose 3 experiments and expected lift ranges."
""",
            encoding="utf-8",
        )
        files.append(p)
    except Exception as e:  # noqa: BLE001
        errors.append(f"prompt_pack.md: {type(e).__name__}: {e}")

    # 3) Scripts folder
    scripts_dir = bonus_dir / "scripts"
    worksheets_dir = bonus_dir / "worksheets"
    _safe_mkdir(scripts_dir)
    _safe_mkdir(worksheets_dir)

    try:
        p = scripts_dir / "outreach_email_templates.md"
        p.write_text(
            f"""# Outreach Email Templates

## Template A — Value-first (cold)
Subject: A practical system to sell '{product.topic}' with crypto checkout

Hi {{Name}},

I built a premium, ops-ready guide for {product.topic}. It includes diagrams, checklists, and a realistic case study.

If you're selling digital products globally, crypto checkout can remove chargebacks and reduce payment friction—when implemented with strong gating and support boundaries.

If helpful, I can share a 1-page summary and the diagram. Interested?

— {{YourName}}

## Template B — Creator collaboration
Subject: Quick collab idea: premium crypto checkout assets

Hi {{Name}},

I’m shipping a premium digital product package that includes:
- diagrams (funnel + system architecture)
- checklists + worksheets
- support macros and promo scripts

If you want, I can provide a co-branded version for your audience.

— {{YourName}}
""",
            encoding="utf-8",
        )
        files.append(p)
    except Exception as e:  # noqa: BLE001
        errors.append(f"outreach_email_templates.md: {type(e).__name__}: {e}")

    try:
        p = scripts_dir / "support_macros.md"
        p.write_text(
            f"""# Support Macros (Copy/Paste)

## 1) Payment Pending
Hi — thanks for your purchase. Your payment is currently pending confirmation.
- Suggested coin/network: {ops['primary_coin']}
- Estimated network fee: ~${ops['avg_network_fee_usd']}
If it stays pending for >20 minutes, reply with your invoice ID and we’ll check.

## 2) Wrong Network / Fee Confusion
Hi — the payment must be sent on the correct network for the selected coin.
If you used the wrong network, the provider may not detect it automatically. Reply with:
- tx hash
- coin + network
- invoice ID

## 3) Paid but Download Issue
Hi — thanks. If the download button fails:
1) Refresh the page
2) Try again in 30 seconds
3) If still failing, reply with invoice ID and order ID.
We will re-issue the download link.

## 4) Refund / Scope
Hi — this product is an execution system with templates and assets.
If you believe it's not a fit, tell us what outcome you expected and we'll help you apply the steps.
""",
            encoding="utf-8",
        )
        files.append(p)
    except Exception as e:  # noqa: BLE001
        errors.append(f"support_macros.md: {type(e).__name__}: {e}")

    try:
        p = scripts_dir / "promo_scripts_shortform.md"
        p.write_text(
            f"""# Short-form Promo Scripts (30–45s)

## Script 1 — Before/After
Hook: "Most crypto digital products feel like summaries. Here's what a premium one looks like."
- Before: vague PDF, no system, no metrics
- After: diagrams + checklists + case study with numbers
CTA: "Link in bio — get the premium package."

## Script 2 — Funnel Metric
Hook: "Your real problem isn't traffic; it's conversion."
Metric: LP→Checkout is often {funnel['lp_to_checkout_pct']}%. If yours is lower, fix hero + proof + CTA.
CTA: "I packaged the full system with diagrams and workflows."

## Script 3 — Gating
Hook: "Chargeback-free payments are great—until you accidentally give the download for free."
Point: server-side paid confirmation + gated delivery
CTA: "Get the ops-ready implementation guide."
""",
            encoding="utf-8",
        )
        files.append(p)
    except Exception as e:  # noqa: BLE001
        errors.append(f"promo_scripts_shortform.md: {type(e).__name__}: {e}")

    # 4) Worksheets (CSV)
    try:
        p = worksheets_dir / "30_60_90_plan.csv"
        p.write_text(
            "Phase,Goal,Tasks,Owner,DueDate,Status,Notes\n"
            "30 days,Baseline + Instrumentation,"
            '"Ship v1; instrument funnel; publish FAQ; stabilize payment + download",'
            '"You",,,,\n'
            "60 days,Optimization + Bundling,"
            '"Run weekly experiments; introduce bundle; refine pricing; track support load",'
            '"You",,,,\n'
            "90 days,Scale + Portfolio,"
            '"Add 3–5 adjacent products; systematize reporting; enforce QC threshold",'
            '"You",,,,\n',
            encoding="utf-8",
        )
        files.append(p)
    except Exception as e:  # noqa: BLE001
        errors.append(f"30_60_90_plan.csv: {type(e).__name__}: {e}")

    try:
        p = worksheets_dir / "funnel_metrics_template.csv"
        p.write_text(
            "Date,Visits,LP_to_Checkout_pct,Checkout_to_Paid_pct,Paid_to_Download_pct,Revenue_usd,Support_tickets\n"
            f",,{funnel['lp_to_checkout_pct']},{funnel['checkout_to_paid_pct']},{funnel['paid_to_download_pct']},,\n",
            encoding="utf-8",
        )
        files.append(p)
    except Exception as e:  # noqa: BLE001
        errors.append(f"funnel_metrics_template.csv: {type(e).__name__}: {e}")

    # 5) Pricing copy blocks (use on landing)
    try:
        p = bonus_dir / "pricing_blocks.md"
        p.write_text(
            """# Pricing Copy Blocks

Use these blocks to improve landing page clarity + perceived value.

## Basic (${price})
- Premium PDF guide (professionally formatted)
- Key diagrams + checklists
- Deterministic build per product_id

## Bundle (${price_plus_20})
- Everything in Basic
- Prompt pack + worksheets + scripts
- 30-day promo calendar

## Pro (${price_plus_40})
- Everything in Bundle
- Benchmarks + troubleshooting matrix
- Launch plan + support macros

**Pro tip:** show *counts* (diagrams, bonus files, promo assets) as proof.
""".replace("{price}", str(int(round(float(meta.get("price_usd", 39))))))
            .replace(
                "{price_plus_20}",
                str(int(round(float(meta.get("price_usd", 39)) + 20))),
            )
            .replace(
                "{price_plus_40}",
                str(int(round(float(meta.get("price_usd", 39)) + 40))),
            ),
            encoding="utf-8",
        )
        files.append(p)
    except Exception as e:  # noqa: BLE001
        errors.append(f"pricing_blocks.md: {type(e).__name__}: {e}")

    # 6) FAQ blocks
    try:
        p = bonus_dir / "faq_blocks.md"
        p.write_text(
            """# FAQ Blocks (Copy/Paste)

## Does this work without a huge audience?
Yes. Use the metrics template and target realistic conversion (1.2–2.8%).

## Which networks/currencies are supported?
List your supported coins and networks clearly. Confusion here is the #1 support driver.

## How do I receive the file after paying?
You get an automated status check + a gated download link (signed token).

## Refund policy?
Define it upfront. Common options: (a) refund before download, (b) credit after download, (c) manual review for wrong-network payments.
""",
            encoding="utf-8",
        )
        files.append(p)
    except Exception as e:  # noqa: BLE001
        errors.append(f"faq_blocks.md: {type(e).__name__}: {e}")

    # 7) A/B test log worksheet
    try:
        ws = bonus_dir / "worksheets"
        ws.mkdir(parents=True, exist_ok=True)
        p = ws / "ab_test_log.csv"
        p.write_text(
            "test_name,start_date,end_date,variant_a,variant_b,metric,decision,notes\n",
            encoding="utf-8",
        )
        files.append(p)
    except Exception as e:  # noqa: BLE001
        errors.append(f"ab_test_log.csv: {type(e).__name__}: {e}")

    # 8) Launch plan
    try:
        p = bonus_dir / "launch_plan.md"
        p.write_text(
            """# 7-Day Launch Plan (Realistic)

Day 1 — Setup
- Connect payment provider, define supported coins/networks, test status loop

Day 2 — Proof blocks
- Add deliverables list, counts, diagrams, and FAQ ordering

Day 3 — Offer packaging
- Create 3-tier pricing + bundle framing

Day 4 — Content engine
- Prepare 10 short scripts + 3 X threads + 1 blog post

Day 5 — Publish + first promo wave
- Post to 2–3 channels, track clicks and checkout starts

Day 6 — Fix top 3 leaks
- Use troubleshooting matrix; reduce support friction

Day 7 — Optimize
- A/B hero + CTA; lock in a weekly iteration loop
""",
            encoding="utf-8",
        )
        files.append(p)
    except Exception as e:  # noqa: BLE001
        errors.append(f"launch_plan.md: {type(e).__name__}: {e}")

    ok = len(errors) == 0
    return BonusBuildResult(ok=ok, errors=errors, files=files)

