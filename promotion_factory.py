# -*- coding: utf-8 -*-
"""
promotion_factory.py

목적(운영용):
- 제품별 홍보 자산을 "플랫폼 업로드 가능한 형태"로 자동 생성한다.
- 생성 결과는 반드시 outputs/<product_id>/promotions/ 아래에 저장한다.
- 외부 API 키가 없어도(=mock) 파일 생성은 100% 수행한다.
- (선택) webhook 전송은 키가 있을 때만 시도한다(스팸/장애 방지).

필수 생성물(요구사항):
- blog_longform.md                 : 블로그 장문 글
- instagram_post.txt               : 인스타 캡션(해시태그 포함)
- shortform_video_script.txt       : TikTok/Reels/Shorts용 1편 스크립트
- sales_page_copy.md               : 세일즈 페이지 카피(구성/FAQ/CTA)

추가 생성물(기존 유지):
- x_posts.txt, reddit_posts.txt, linkedin_posts.txt, newsletter_email.txt, seo.txt
- x_threads.txt, shortform_scripts.txt, blog_outline.md, blog_post.md, promo_calendar_30d.csv
- promo_pack.zip, promotion_manifest.json
"""

from __future__ import annotations

import hashlib  # 결정적 seed
import json  # manifest 저장
import random  # 텍스트 변형
import time  # 타임스탬프
import zipfile  # promo_pack.zip
from pathlib import Path  # 경로
from typing import Dict, List, Tuple  # 타입

try:
    from src.promotion_validator import PromotionValidator
except ImportError:
    # Fallback if src is not in path
    import sys
    sys.path.append(str(Path(__file__).resolve().parent))
    from src.promotion_validator import PromotionValidator

def _utc_iso() -> str:
    """UTC ISO 문자열."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _seed_from_product_id(product_id: str) -> int:
    """product_id로부터 seed를 만든다(결정적)."""
    digest = hashlib.sha256(product_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big", signed=False)


def _write(path: Path, text: str) -> None:
    """텍스트 파일 저장(항상 \n으로 끝나게)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text((text or "").rstrip() + "\n", encoding="utf-8")


def _atomic_write_json(path: Path, obj) -> None:
    """JSON 원자 저장."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


# -----------------------------
# Generators (assets)
# -----------------------------



def _gen_medium_hybrid_story(rng: random.Random, title: str, topic: str, price_usd: float, product_id: str) -> str:
    """
    Generates a Hybrid (Informational + Promotional) Article for Revenue-Driven Blogs.
    Target: AdSense approval, SEO ranking, and soft-selling.
    Structure: 70% Value / 30% Promotion.
    """
    
    # 1. Informational Titles (Search Intent Driven)
    info_titles = [
        f"The Ultimate Guide to {topic}: Everything You Need to Know",
        f"How to Master {topic} in 2025: A Step-by-Step Tutorial",
        f"5 Proven Strategies for {topic} Success (Beginner to Pro)",
        f"What Experts Aren't Telling You About {topic}",
        f"Top 10 Tools for {topic} That Will Save You Hours"
    ]
    selected_title = rng.choice(info_titles)
    
    # 2. Educational Intro (No selling yet)
    intros = [
        f"In the rapidly evolving world of digital business, **{topic}** has become a cornerstone for success. Whether you are a solo entrepreneur or a scaling startup, understanding the nuances of {topic} can be the difference between stagnation and growth.",
        f"Have you ever wondered why some creators seem to succeed effortlessly with {topic} while others struggle? The secret often lies not in working harder, but in leveraging the right strategies and tools. In this comprehensive guide, we'll explore exactly how to master {topic}.",
        f"**{topic}** is no longer just a buzzword—it's a fundamental shift in how we approach value creation online. But with so much conflicting information out there, where do you start? I've spent months analyzing the best practices, and here is what I found."
    ]
    intro = rng.choice(intros)
    
    # 3. Value Sections (The "Meat" of the article)
    value_points = [
        "### 1. Understand the Fundamentals First\nBefore diving into complex tactics, ensure your foundation is solid. The most successful implementations of this concept start with a clear clear strategy and defined goals.",
        "### 2. Automation is Key\nManual processes are the enemy of scale. By automating repetitive tasks, you free up creative energy for what really matters—innovation and connection.",
        "### 3. Data-Driven Decisions\nStop guessing. Use analytics to understand what works. The top 1% of performers in this niche always rely on data, not just intuition.",
        "### 4. Consistency Over Intensity\nIt's better to show up every day with small improvements than to burn out after one week of intense effort. Building a sustainable system is crucial."
    ]
    # Shuffle and pick 3
    rng.shuffle(value_points)
    body_content = "\n\n".join(value_points[:3])
    
    # 4. Soft Transition ( The "Bridge" )
    bridges = [
        "While these strategies are powerful, implementing them from scratch can be overwhelming. You might find yourself spending hours on technical setup instead of growing your business. This is where having the right tool changes everything.",
        "However, there is a catch. Doing all of this manually requires significant time and technical expertise. Fortunately, new solutions have emerged that streamline this entire process.",
        "You could try to build this system yourself, stitching together various disparate tools. Or, you could use a unified solution designed specifically for this purpose."
    ]
    bridge = rng.choice(bridges)
    
    # 5. Product Introduction (The Solution)
    product_pitch = f"""
### The Solution: {title}

If you are looking for a way to fast-track your results with {topic}, I highly recommend checking out **[{title}](https://metapassiveincome.com/product/{product_id})**.

This tool is designed to handle the heavy lifting for you.
- **Automated Workflow:** Save hours every week.
- **Proven Templates:** Don't reinvent the wheel.
- **Cost-Effective:** At just **${price_usd:.2f}**, it costs less than a single hour of a consultant's time.

I personally use this to streamline my operations, and it has been a game-changer for my productivity.
"""

    # 6. Conclusion
    outro = f"""
### Final Thoughts

Mastering **{topic}** is a journey, not a destination. By applying the principles outlined above—focusing on fundamentals, leveraging automation, and using the right tools like {title}—you can achieve significant results.

Start small, be consistent, and don't be afraid to use tools that give you an unfair advantage.

*Disclaimer: This article contains affiliate links. If you purchase through these links, I may earn a commission at no additional cost to you. I only recommend products I believe in.*
"""

    return f"""# {selected_title}

{intro}

{body_content}

{bridge}

{product_pitch}

{outro}
"""

def _gen_medium_story(rng: random.Random, title: str, topic: str, price_usd: float) -> str:

    """Medium용 스토리텔링 아티클 생성"""
    
    # 1. Title Variations (Hook-based)
    titles = [
        f"Why I Finally Ditched Traditional Payments for {topic}",
        f"The Ugly Truth About Selling Digital Products (And How {topic} Fixes It)",
        f"How to Build a {topic} Empire Without Writing a Single Line of Code",
        f"I Tested 5 Payment Gateways. Here's Why Crypto Won.",
        f"The Passive Income Blueprint No One Is Talking About: {topic}"
    ]
    selected_title = rng.choice(titles)
    
    # 2. Introduction (Personal/Problem)
    intros = [
        "I still remember the first time I got a chargeback. It wasn't just about the money—it was the feeling of powerlessness.",
        "Let's be honest: The traditional e-commerce stack is broken. Middlemen, fees, and delays are killing your margins.",
        "Everyone talks about passive income, but nobody tells you about the operational nightmare of fulfilling orders manually."
    ]
    intro = rng.choice(intros)
    
    # 3. Body
    # Enhance body with Key Takeaways and FAQ for "informational" value
    
    key_takeaways = [
        "**Instant Settlement:** How blockchain removes the 3-5 day wait for funds.",
        "**Chargeback Protection:** Why crypto is the only way to truly prevent friendly fraud.",
        "**Global Access:** Selling to 100% of the world, not just the banked 60%.",
        "**Automation:** The tech stack that delivers files 24/7 without human input."
    ]
    
    faq_section = """
    ## Frequently Asked Questions

    **Q: Is this difficult to set up?**
    A: Not with the right tools. The {topic} blueprint is designed to be copy-paste.

    **Q: What about volatility?**
    A: You can accept stablecoins (USDT/USDC) to avoid market fluctuations completely.

    **Q: Do I need to be a developer?**
    A: No. If you can copy code snippets, you can run this system.
    """

    body = f"""
# {selected_title}

{intro}

## Key Takeaways
{chr(10).join(['* ' + k for k in key_takeaways])}

---

For years, I struggled with the friction of selling digital assets. I wanted a system that was clean, automated, and global. I didn't want to wake up to support emails asking "Where is my file?"

That's why I dove deep into **{topic}**.

## The Problem with the "Old Way"

If you're selling digital products today, you're likely dealing with:
*   **High Fees:** Payment processors taking 3-5% plus fixed fees.
*   **Chargebacks:** Friendly fraud that eats your profits.
*   **Global Barriers:** Customers in certain countries can't even buy from you.

I knew there had to be a better way. I wanted **deterministic delivery**—a system where code guarantees the outcome, not a human.

## Enter the {topic} Solution

I spent months refining a workflow that leverages blockchain technology for instant, trustless settlements. It's not just about "accepting crypto"—it's about automating the entire lifecycle of a digital sale.

Here is what I discovered:
1.  **Speed is King:** When you remove the banks, settlement is instant.
2.  **Privacy Matters:** Buyers appreciate the option to pay without handing over their life story.
3.  **Automation is Freedom:** A script never sleeps. It delivers the product at 3 AM just as reliably as at 3 PM.

## How You Can Do It Too

You don't need to be a solidity developer to set this up. The principles are simple:
*   Use a non-custodial wallet or a direct payment gateway.
*   Gate your content with signed tokens.
*   Automate the email follow-up.

I've packaged everything I learned into a comprehensive system called **{title}**. It's the exact blueprint I wish I had when I started.

## What's Inside {title}?

*   **The Playbook:** Step-by-step guide to setting up your automated store.
*   **The Code:** Copy-paste templates for your sales page and delivery logic.
*   **The Strategy:** How to market to a privacy-conscious audience.

{faq_section}

> "The best time to build a sovereign business was yesterday. The second best time is now."

## Ready to Automate?

If you're tired of the old way and want to build a truly passive, global digital business, check out the full bundle.

[👉 **Get the {topic} Automation Blueprint Here**]({{preview_url}})

*P.S. This is available for a limited time at ${price_usd:.0f}. Grab it before the price goes up.*

---
*Disclaimer: This article is for educational purposes only. Always do your own research before setting up financial systems.*
"""
    return body

def _gen_30_day_calendar(rng: random.Random, title: str, topic: str) -> str:
    """30일 프로모션 캘린더 CSV."""
    channels = [
        "Blog",
        "Instagram",
        "TikTok",
        "YouTube Shorts",
        "X",
        "Reddit",
        "LinkedIn",
    ]
    hooks = [
        "🔥 Stop losing 3% to card fees — Settle globally in seconds, not days.",
        "🔒 Privacy is a feature, not a luxury. Reduce payment traceability today.",
        "🚀 Turn your crypto wallet into a high-performance revenue engine.",
        "⚠️ The #1 mistake digital sellers make with crypto (and how to fix it).",
        "💎 From zero to automated crypto sales: The exact 7-day blueprint.",
        "📈 Double your conversion rates with 'Trust Blocks' + Proof Metrics.",
        "🌍 Global commerce without boundaries: Sell to anyone, anywhere, instantly.",
    ]
    ctas = [
        "👉 Grab the Premium Bundle + Secret Templates [Limited Time]",
        "📥 Download the complete system and launch your store today.",
        "🛠 Copy my exact workflow and start shipping by tonight.",
        "✅ Get the checklist and avoid the expensive mistakes I made.",
        "💰 Start accepting crypto like a pro — Download now.",
    ]
    keywords = [
        "crypto automation, instant settlement, web3 commerce",
        "digital product delivery, privacy-first payments, conversion optimization",
        "nowpayments integration, automated fulfillment, high-ticket sales",
        "sales funnel design, trust-building metrics, automated operations",
        "passive income system, crypto revenue, digital entrepreneurship",
    ]
    rows = ["day,channel,hook,cta,keywords"]
    for day in range(1, 31):
        ch = rng.choice(channels)
        hk = rng.choice(hooks)
        cta = rng.choice(ctas)
        kw = rng.choice(keywords)
        rows.append(f'{day},{ch},"{hk}","{cta}","{kw}"')
    return "\n".join(rows) + "\n"


def _gen_x_threads(rng: random.Random, title: str, topic: str) -> str:
    """X/Twitter 10-트윗 스레드 3개 (고도로 최적화된 마케팅 구조)."""
    threads = []
    for t in range(1, 4):
        lines = [f"🧵 THREAD {t}/3: How to dominate the {topic} market using Crypto."]
        lines.append(
            "1/ If you're selling digital products but still relying on card processors, you're leaving money on the table. 💸"
        )
        lines.append(
            "2/ The biggest hurdle for buyers isn't the price—it's the friction. Crypto removes the middleman and the hesitation. 🔓"
        )
        lines.append(
            "3/ Most 'crypto checkouts' look sketchy. That's why your conversion dies at the finish line. You need 'Trust Blocks'. 🧱"
        )
        lines.append(
            "4/ A Trust Block isn't just a logo. It's real-time payment status, deterministic delivery, and clear support boundaries. 🛡️"
        )
        lines.append(
            "5/ Our state-machine architecture ensures that NO customer is left behind. Paid = Delivered. Automatically. ⚡"
        )
        lines.append(
            "6/ We use signed, time-limited download tokens. Stop people from sharing your hard work for free. 🔒"
        )
        lines.append(
            "7/ Support tickets kill your time. Our system includes a 'Troubleshooting Matrix' that solves 90% of issues before they're asked. 🤖"
        )
        lines.append(
            "8/ Imagine a business that settles globally, has 0 chargebacks, and runs 24/7 while you sleep. That's the power of this system. 🌍"
        )
        lines.append(
            "9/ We've packaged the exact blueprint, templates, and automation scripts into one 'Meta Passive Income' bundle. 📦"
        )
        lines.append(f"10/ Stop building, start shipping. Grab {title} now and join the new era of commerce. 👇 [Link in Bio]")
        threads.append("\n".join(lines))
    return "\n\n---\n\n".join(threads) + "\n"


def _gen_shortform_scripts(rng: random.Random, title: str, topic: str) -> str:
    """Shorts/TikTok용 10개 스크립트 (시청 지속시간 및 전환 최적화)."""
    scripts = []
    for i in range(1, 11):
        hook = rng.choice(
            [
                "🛑 Stop! You're losing sales because your checkout looks like a 1990s scam.",
                "Imagine selling to anyone in the world, instantly, with zero bank interference. 🌍",
                "The secret to a $10k/month digital product business isn't more traffic—it's this. 👇",
                "Why high-ticket sellers are switching to crypto-only checkouts in 2026. 🚀",
            ]
        )
        body = rng.choice(
            [
                "You need a 'Trust-First' funnel. Real-time status, signed tokens, and automated fulfillment. It's not magic, it's just better tech.",
                "Bank chargebacks are a hidden tax on your hard work. Crypto fixes this. Instant settlement, zero disputes, pure profit.",
                "Most people fail because they can't handle the ops. Our system automates everything from payment to delivery to support.",
                "Privacy-first buyers are the most loyal. Give them the wallet-native experience they've been waiting for.",
            ]
        )
        proof = rng.choice(
            [
                "We include the full PDF playbook, automated scripts, and a 30-day promo calendar to get you started TODAY.",
                "This isn't just theory. It's the exact system we use to run a global digital empire with zero employees.",
                "Get the templates, the code, and the marketing copy. It's a business-in-a-box for the web3 era.",
            ]
        )
        cta = rng.choice(
            [
                "🚀 Grab the bundle now — Link in bio!",
                "💎 Don't wait for the banks to catch up. Launch today.",
                "📥 Instant download. No waiting. Start shipping now.",
            ]
        )
        scripts.append(
            "\n".join(
                [
                    f"SCRIPT {i}",
                    f"🪝 HOOK: {hook}",
                    f"📝 BODY: {body}",
                    f"📊 PROOF: {proof}",
                    f"💰 CTA: {cta}",
                ]
            )
        )
    return "\n\n---\n\n".join(scripts) + "\n"


def _gen_blog_assets(rng: random.Random, title: str, topic: str, preview_url: str = "#", screenshot_url: str = "") -> Tuple[str, str]:
    """블로그 개요 + 장문 본문 (SEO 최적화 + 구글 친화적 구조 + 판매 유도 강화)."""
    
    # SEO용 키워드 추출 (제목과 주제 기반)
    primary_kw = f"{topic} automation"
    secondary_kws = ["crypto checkout", "digital product delivery", "passive income system", "instant settlement"]
    
    # 1. 블로그 개요 (구조화된 SEO Blueprint)
    outline = "\n".join(
        [
            f"# SEO Content Blueprint — {title}",
            f"**Primary Keyword:** {primary_kw}",
            f"**Secondary Keywords:** {', '.join(secondary_kws)}",
            "",
            "## Content Structure:",
            "1. H1: SEO-Optimized Title with Value Proposition",
            "2. Meta Description: High-CTR summary for Google SERP",
            "3. Executive Summary: 'Key Takeaways' for quick consumption",
            "4. H2: The Problem (Identifying Pain Points)",
            "5. H2: The Solution (Introducing the Blueprint)",
            "6. H3: Visual Proof & Architecture",
            "7. H2: Why This System? (Unique Selling Points)",
            "8. H2: FAQ (SEO Schema Friendly)",
            "9. H2: Conclusion & Final CTA",
        ]
    )

    # placeholder if no screenshot
    # 제품 주제(topic)와 관련된 이미지를 찾기 위해 검색 쿼리 최적화
    if not screenshot_url:
        # 주제어에서 핵심 키워드 추출 (공백 기준)
        search_query = topic.replace(" ", "+")
        # 결정적 시드를 사용하여 Unsplash 이미지 선택 (동적성 부여)
        # rng가 product_id 기반 seed를 가지므로, 항상 동일한 product_id에 대해 동일한 img_seed 생성
        img_seed = rng.randint(1, 1000)
        img_url = f"https://images.unsplash.com/featured/?{search_query},technology,business&sig={img_seed}"
    else:
        img_url = screenshot_url
    
    # 2. 장문 본문 (SEO + Sales 최적화)
    # Meta Description (Google이 검색 결과에 표시할 요약문)
    meta_desc = f"Discover how to automate your {topic} business with {title}. A trust-first crypto commerce blueprint designed for instant delivery and high conversion. Download the full bundle today."
    
    # 판매 유도 주소 (Live 링크) 강조를 위한 버튼 텍스트
    cta_button_text = f"🚀 GET INSTANT ACCESS TO {title.upper()}"
    
    # 본문 구성요소 (결정적 무작위성 가미)
    benefits = [
        f"- **Instant Settlement:** Zero waiting for bank transfers; get paid in crypto instantly.",
        f"- **Deterministic Delivery:** Automated {topic} fulfillment the second payment is confirmed.",
        "- **Trust-First Design:** Engineered to convert skeptical buyers with visual proof and state-machine certainty.",
        f"- **Scalable Passive Income:** Run a global {topic} empire with zero employee overhead.",
        "- **Privacy-First:** Secure your IP and your buyers' data with advanced encryption protocols."
    ]
    rng.shuffle(benefits) # seed 기반이므로 항상 동일하게 섞임
    selected_benefits = benefits[:4]

    body = "\n".join(
        [
            f"# {title}: The Definitive {topic} Automation Blueprint for 2026",
            "",
            f"> **Meta Description:** {meta_desc}",
            "",
            "---",
            "",
            "## 💡 Key Takeaways (Executive Summary)",
            *selected_benefits,
            "",
            "---",
            "",
            "## 🛑 The Friction: Why Most Digital Sellers Fail with Crypto",
            "The biggest barrier to scaling a digital product business isn't the product itself—it's the **friction at the finish line.** Most crypto checkouts are clunky, slow, and feel 'scammy.' If your buyer doesn't feel 100% certain about the delivery, they won't click 'Pay.'",
            "",
            f"### The {topic} Market Opportunity",
            f"In the current economy, buyers are moving towards privacy-first, decentralized payments. If you're not offering a seamless, automated way to buy your {topic} assets, you're leaving 40-60% of your potential revenue on the table.",
            "",
            f"![{title} Premium Dashboard Preview]({img_url} \"{title} - High Conversion Dashboard\")",
            f"### [🔥 EXPLORE THE LIVE SYSTEM: See the conversion engine in action]({preview_url})",
            f"#### [👉 {cta_button_text}]({preview_url})",
            "",
            "---",
            "",
            f"## 🛠 The Solution: {title} Trust-First Architecture",
            "We've engineered a system that treats crypto as a first-class citizen, not an afterthought. This isn't just a guide; it's a technical and marketing framework for high-ticket commerce.",
            "",
            "### 1. Visual Proof & Deterministic Logic",
            "Our architecture uses a robust **State Machine** to track every order from 'Initiated' to 'Delivered.' No manual intervention required.",
            "",
            f"![Full Architecture Blueprint]({img_url} \"{topic} Automation System Architecture\")",
            f"#### [👉 {cta_button_text}]({preview_url})",
            "",
            "### 2. Engineering Certainty",
            "- **Real-time Monitoring:** Blockchain confirmation tracking with instant UI feedback.",
            "- **Signed Tokens:** Secure, time-limited download links generated on-the-fly.",
            "- **Zero Chargebacks:** The security of crypto combined with the professionalism of SaaS.",
            "",
            "---",
            "",
            "## ❓ Frequently Asked Questions (FAQ)",
            "",
            f"### Q1: Is this {topic} blueprint suitable for beginners?",
            "**A:** Absolutely. While the tech is advanced, the implementation is designed to be 'plug-and-play.' We provide the code, the copy, and the 30-day roadmap.",
            "",
            "### Q2: How does the instant delivery work?",
            "**A:** The system monitors the blockchain. As soon as the transaction is verified, our fulfillment engine issues a unique, signed download token directly to the buyer.",
            "",
            "### Q3: What is included in the bundle?",
            f"**A:** You get the full PDF playbook, automated delivery scripts, high-converting sales page copy, and a complete 30-day marketing calendar for {topic}.",
            "",
            "---",
            "",
            "## 💰 Claim Your Competitive Advantage",
            f"The **{title}** system is your shortcut to a professional, automated, and high-revenue {topic} business. Stop fighting legacy banking and start building for the future.",
            "",
            f"### [🚀 DOWNLOAD THE COMPLETE {title.upper()} BUNDLE NOW]({preview_url})",
            f"#### [👉 CLICK HERE TO ACCESS {title.upper()} INSTANTLY]({preview_url})",
            "*Join the elite 1% of digital sellers using deterministic, trust-first automation.*",
            "",
            "---",
            "**Google Search Note:** This content is part of the Meta Passive Income series, focused on blockchain commerce and digital asset automation. All benchmarks and results are based on internal testing and industry averages.",
        ]
    )
    return outline + "\n", body + "\n"


def _gen_instagram_post(
    rng: random.Random, title: str, topic: str, price_usd: float
) -> str:
#     """인스타용 캡션 (비주얼 중심 및 강력한 후킹)."""
    hooks = [
        "🔥 Wallet buyers don't want 'trust me' — they want PROOF.",
        "🚀 Selling digital products for crypto? Fix your delivery or lose sales.",
        "🔒 Stop leaking downloads. Gate your IP with signed tokens.",
        "💰 Chargeback-free doesn't mean zero support. Build boundaries.",
    ]
    bullets = [
        "✅ Instant delivery (Deterministic fulfillment)",
        "✅ Token-gated downloads (Protect your IP)",
        "✅ Full Ops Blueprint (Checklists + Templates)",
        "✅ Troubleshooting Matrix (Reduce support by 90%)",
    ]
    hashtags = "#crypto #web3 #digitalproducts #passiveincome #solopreneur #stablecoins #nowpayments #automation #digitalmarketing"

    hook = rng.choice(hooks)
    return (
        "\n".join(
            [
                hook,
                "",
                f"💎 {title}",
                f"💵 Price: ${price_usd:.0f} (Pay with any major crypto)",
                "",
                "The exact system we use to run a global digital goods empire with zero employees and zero bank friction. 🌍",
                "",
                "What's inside:",
                *[f"  {b}" for b in bullets],
                "",
                "👉 Link in Bio — Instant access after payment.",
                "",
                hashtags,
            ]
        )
        + "\n"
    )


def _gen_sales_page_copy(
    rng: random.Random, title: str, topic: str, price_usd: float, preview_url: str = "#", screenshot_url: str = ""
) -> str:
    """세일즈 페이지 카피 (전환 최적화 및 구조화)."""
    faqs = [
        (
            "How do I receive the files?",
            "Immediately after the transaction is confirmed on the blockchain, you will be redirected to a secure download page. You will also receive an email with a signed, time-limited download token.",
        ),
        (
            "What if my payment is pending?",
            "Our automated state machine monitors the blockchain in real-time. As soon as the network confirms your payment, the system automatically triggers fulfillment.",
        ),
        (
            "Is there a support system?",
            "Yes. We include a comprehensive Troubleshooting Matrix that covers 90% of common user issues. For anything else, our support macros help you resolve issues in seconds.",
        ),
        (
            "Why crypto only?",
            "To provide a privacy-first, borderless experience with zero chargebacks and instant global settlement. This is the future of digital commerce.",
        ),
    ]

    img_url = screenshot_url or "https://images.unsplash.com/photo-1639762681485-074b7f938ba0?q=80&w=2000&auto=format&fit=crop"

    return (
        "\n".join(
            [
                f"# {title}",
                "### The Professional Blueprint for Automated Crypto Revenue",
                "",
                f"![Product Preview]({img_url})",
                "",
                f"**Investment:** ${price_usd:.0f} (Crypto-Native Checkout)",
                "",
                "---",
                "",
                "## 🚀 The Outcome",
                "Deploy a high-converting, trust-first crypto checkout and delivery pipeline. This system is designed to convert skeptical wallet buyers into loyal customers while reducing your operational overhead by up to 90%.",
                "",
                f"![System Preview]({img_url})",
                "",
                "## 📦 What's Inside the Bundle",
                "- 📘 **Premium PDF Playbook:** The full operational runbook.",
                "- 🛠 **The Ops Toolkit:** Checklists, KPI trackers, and troubleshooting matrices.",
                "- 📣 **The Marketing Pack:** Pre-written blog posts, social media scripts, and a 30-day calendar.",
                "- 🔐 **Security Protocols:** How to implement signed download tokens and server-side gating.",
                "",
                "## 🎯 Who Is This For?",
                "- **Digital Entrepreneurs:** Who want to escape the 3% card fee tax and bank freezes.",
                "- **Web3 Developers:** Who need a proven marketing and ops layer for their products.",
                "- **Content Creators:** Who want a privacy-first way to monetize their audience globally.",
                "",
                "## 🏗 The 'Certainty' Mechanism",
                "1. **Trust-First Design:** Proof blocks and transparency at every step.\n2. **Automated State Machine:** Deterministic order tracking (Initiated → Paid → Delivered).\n3. **IP Protection:** Signed, short-lived download tokens to prevent sharing.\n4. **Support Automation:** Canned macros and a logic-based troubleshooting matrix.",
                "",
                "---",
                "",
                "## ❓ Frequently Asked Questions",
                *[f"**Q: {q}**\n\n**A:** {a}\n" for (q, a) in faqs],
                "",
                "## 💰 Your New Era Starts Now",
                "Don't let legacy banking friction slow down your growth. Adopt the system built for the next decade of digital goods.",
                "",
                f"### [Download {title} and Launch Today]({preview_url})",
                f"![Final CTA Preview]({img_url})",
            ]
        )
        + "\n"
    )


def _pick_first_shortform(shortform_scripts_text: str) -> str:
    """shortform_scripts.txt에서 SCRIPT 1 블록만 추출(없으면 전체)."""
    parts = shortform_scripts_text.split("\n\n---\n\n")
    if parts:
        return parts[0].strip() + "\n"
    return shortform_scripts_text.strip() + "\n"


# -----------------------------
# Public API
# -----------------------------


def generate_promotions(
    product_dir: Path, product_id: str, title: str, topic: str, price_usd: float
) -> Dict[str, object]:
    """
    promotions 폴더에 홍보 텍스트를 생성한다.
    반환: meta(직렬화 가능한 dict)
    """
    promo_dir = product_dir / "promotions"
    promo_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(_seed_from_product_id(product_id))

    # Deployment URL과 Screenshot URL을 가져오기 위해 manifest.json 읽기 시도
    preview_url = "#"
    screenshot_url = ""
    manifest_path = product_dir / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            preview_url = manifest.get("metadata", {}).get("deployment_url", "#")
            screenshot_url = manifest.get("metadata", {}).get("screenshot_url", "")
        except Exception:
            pass

    # 루프를 통한 검증 및 재생성 로직 (최대 3회)
    best_blog_md = ""
    best_validation = None
    
    for attempt in range(1, 4):
        # 1. 에셋 생성
        outline_md, blog_md = _gen_blog_assets(
            rng, title=title, topic=topic, preview_url=preview_url, screenshot_url=screenshot_url
        )
        
        # 2. 검증 수행
        validation = PromotionValidator.validate_blog_post(blog_md, title)
        
        if validation.passed:
            best_blog_md = blog_md
            best_validation = validation
            break
        else:
            if not best_blog_md or validation.score > (best_validation.score if best_validation else 0):
                best_blog_md = blog_md
                best_validation = validation
            # 실패 시 seed를 변경하여 다음 시도에서 다른 텍스트 유도
            rng = random.Random(rng.randint(0, 1000000))
    
    blog_md = best_blog_md

    # 기본 채널 카피
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
    for _ in range(3):
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

    # 프리미엄 확장
    _write(promo_dir / "x_threads.txt", _gen_x_threads(rng, title=title, topic=topic))
    shortform_lib = _gen_shortform_scripts(rng, title=title, topic=topic)
    _write(promo_dir / "shortform_scripts.txt", shortform_lib)


    # Medium Story 생성 (Hybrid for Revenue)
    medium_story = _gen_medium_hybrid_story(rng, title=title, topic=topic, price_usd=price_usd, product_id=product_id)
    _write(promo_dir / "medium_story.md", medium_story)

    # _gen_blog_assets은 위에서 루프를 통해 생성되었으므로 outline_md만 다시 생성하거나 가져옴
    _write(promo_dir / "blog_outline.md", outline_md)
    _write(promo_dir / "blog_post.md", blog_md)

    _write(
        promo_dir / "promo_calendar_30d.csv",
        _gen_30_day_calendar(rng, title=title, topic=topic),
    )

    # -----------------------------
    # 요구사항: 플랫폼 업로드용 파일명(고정)
    # -----------------------------
    _write(promo_dir / "blog_longform.md", blog_md)  # 장문 블로그
    _write(
        promo_dir / "instagram_post.txt",
        _gen_instagram_post(rng, title=title, topic=topic, price_usd=price_usd),
    )
    _write(
        promo_dir / "instagram.txt",
        _gen_instagram_post(rng, title=title, topic=topic, price_usd=price_usd),
    )
    _write(
        promo_dir / "shortform_video_script.txt", _pick_first_shortform(shortform_lib)
    )  # 1편만
    _write(
        promo_dir / "sales_page_copy.md",
        _gen_sales_page_copy(rng, title=title, topic=topic, price_usd=price_usd),
    )

    # promo_pack.zip 생성(폴더 내 파일 전체 압축)
    promo_zip = promo_dir / "promo_pack.zip"
    with zipfile.ZipFile(promo_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(promo_dir.glob("*")):
            if p.name == "promo_pack.zip":
                continue
            if p.is_file():
                z.write(p, p.name)

    meta = {
        "product_id": product_id,
        "created_at": _utc_iso(),
        "files": sorted([p.name for p in promo_dir.glob("*") if p.is_file()]),
        "validation": best_validation.to_dict() if best_validation else None
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


# -----------------------------
# Optional webhook publish (safe)
# -----------------------------

import os  # noqa: E402  (env)

import requests  # noqa: E402  (optional)


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

    results: Dict[str, object] = {
        "product_id": product_id,
        "created_at": _utc_iso(),
        "sent": [],
    }

    tg = os.getenv("TELEGRAM_WEBHOOK_URL", "").strip()
    dc = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

    if tg:
        ok = _safe_post_json(tg, {"text": text})
        results["sent"].append({"channel": "telegram_webhook", "ok": ok})

    if dc:
        ok = _safe_post_json(dc, {"content": text})
        results["sent"].append({"channel": "discord_webhook", "ok": ok})

    promo_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(promo_dir / "publish_results.json", results)
    return results
