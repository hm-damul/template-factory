# -*- coding: utf-8 -*-
"""
niche_data.py
공통 분야별(Niche) 콘텐츠 및 템플릿 데이터.
"""

NICHE_CONTENT_MAP = {
    "finance": {
        "mistakes": [
            "Using static pricing in a volatile market without clear fee guidance.",
            "Lack of transparency in transaction fees and settlement times.",
            "Failing to provide a 'Safe Mode' or 'Risk Warning' for financial tools.",
        ],
        "expert_notes": [
            "In finance, trust is the only currency that matters. Over-communicate on security.",
            "Always include a 'Reconciliation Guide' for users to track their own transactions.",
        ],
        "pro_tips": [
            "Add a 'Fee Calculator' to the checkout to reduce abandonment due to surprise gas fees.",
            "Bundle a 'Tax Compliance Checklist' to increase perceived value for high-ticket buyers.",
        ],
        "schema_templates": {
            "problem": "Financial operators struggle with manual reporting, volatile fees, and complex compliance. Without a professional system, trust decays and conversion drops.",
            "solution": "A hardened financial toolkit with automated tracking, fee-optimized checkout, and built-in compliance checklists. Designed for high-trust transactions.",
            "features": [
                "Fee-optimized wallet checkout",
                "Automated transaction reconciliation log",
                "Compliance & Tax reporting templates",
                "Real-time network fee estimator",
                "Secure, idempotent delivery system"
            ]
        }
    },
    "productivity": {
        "mistakes": [
            "No 'Quick Start' guide; TTV (Time to Value) should be under 5 minutes.",
            "Static templates that don't adapt to different user scales.",
            "Over-complicating the UI before solving the core friction point.",
        ],
        "expert_notes": [
            "The best productivity tools are invisible. Focus on seamless integration.",
            "Measure success by how much time your user SAVES, not how much time they spend in-app.",
        ],
        "pro_tips": [
            "Include a '1-Click Import' feature for popular platforms (Notion, Trello, etc.).",
            "Add 'Batch Processing' scripts to help users handle large volumes of work instantly.",
        ],
        "schema_templates": {
            "problem": "Modern workflows are fragmented and manual. Users waste hours on repetitive tasks that should be automated, leading to burnout and inefficiency.",
            "solution": "A seamless productivity engine that automates the heavy lifting. Includes ready-to-use templates, batch scripts, and a clear roadmap to 10x output.",
            "features": [
                "1-Click workflow automation templates",
                "Batch processing & script library",
                "Time-saving integration hooks",
                "Customizable milestone trackers",
                "Minimalist, friction-free UI/UX"
            ]
        }
    },
    "marketing": {
        "mistakes": [
            "Focusing on features instead of outcomes in the first 100 words.",
            "No social proof or results-based evidence in the above-the-fold section.",
            "Vague CTAs that don't tell the user exactly what happens next.",
        ],
        "expert_notes": [
            "Marketing is not about trickery; it's about clarity of value.",
            "The best copy is written by your customers. Use their exact words and pain points.",
        ],
        "pro_tips": [
            "Use 'Power Words' that trigger emotional responses (e.g., 'Instant', 'Hardened', 'Proven').",
            "A/B test your headline every 500 visits to find the winning hook.",
        ],
        "schema_templates": {
            "problem": "Most marketing assets are generic and fail to convert. Without a high-converting system, traffic is wasted and acquisition costs skyrocket.",
            "solution": "A results-driven marketing vault with proven hooks, structured landing templates, and conversion-optimized copy. Designed for rapid scale.",
            "features": [
                "High-converting hook & headline library",
                "A/B test ready landing page templates",
                "Psychology-based sales copy frameworks",
                "Social proof & proof-block templates",
                "Multi-channel promotion sequences"
            ]
        }
    },
    "ai_automation": {
        "mistakes": [
            "Using over-generalized prompts that result in bland, generic outputs.",
            "Ignoring error handling for API timeouts or rate limits (429s).",
            "Lack of human-in-the-loop validation for critical data extraction.",
        ],
        "expert_notes": [
            "AI is a force multiplier, not a replacement for domain expertise.",
            "The quality of AI output is 80% data preparation and 20% prompt engineering.",
        ],
        "pro_tips": [
            "Implement 'Self-Healing' prompts that retry on validation failure.",
            "Use few-shot prompting with concrete examples to increase accuracy by 30%.",
        ],
        "schema_templates": {
            "problem": "Manual AI workflows are slow and error-prone. Without a structured automation system, scaling AI-driven tasks leads to inconsistent quality and high operational costs.",
            "solution": "A robust AI automation framework with pre-built prompt templates, error-handling logic, and automated quality gates. Designed for high-scale AI operations.",
            "features": [
                "Hardened prompt engineering library",
                "Automated quality gate & validation logic",
                "Rate-limit & retry handling system",
                "Structured output (JSON/Markdown) templates",
                "AI-to-Human handoff workflows"
            ]
        }
    },
    "ecommerce": {
        "mistakes": [
            "Ignoring mobile checkout friction; 70% of users drop off on small screens.",
            "Hidden shipping or fee costs revealed too late in the funnel.",
            "Slow page load times; every 1s delay reduces conversion by 7%.",
        ],
        "expert_notes": [
            "E-commerce is about reducing friction. Every click is a chance to lose a customer.",
            "Visual hierarchy should lead the eye directly to the 'Add to Cart' button.",
        ],
        "pro_tips": [
            "Use 'Scarcity' and 'Urgency' triggers (e.g., 'Only 3 left', 'Sale ends in 2h').",
            "Implement 'One-Click Checkout' to increase conversion for returning users.",
        ],
        "schema_templates": {
            "problem": "Generic e-commerce stores fail to build trust and suffer from high cart abandonment. Without a high-performance storefront, conversion remains stagnant.",
            "solution": "A conversion-optimized e-commerce engine with mobile-first UI, friction-free checkout, and built-in trust triggers. Built for modern digital merchants.",
            "features": [
                "Mobile-optimized high-speed landing UI",
                "Trust-building proof & badge templates",
                "Frictionless 1-click checkout flow",
                "Automated order confirmation & tracking",
                "Urgency & scarcity trigger system"
            ]
        }
    },
    "web3": {
        "mistakes": [
            "Assuming users understand gas fees; always explain the 'Network Fee' in simple terms.",
            "Relying solely on hot wallets for business treasury management.",
            "Lack of clear 'Transaction Pending' UI, leading to multiple unnecessary clicks.",
        ],
        "expert_notes": [
            "In Web3, transparency is the foundation of trust. Show every on-chain step.",
            "Decentralization is a feature, not a barrier. Make it feel like a normal web experience.",
        ],
        "pro_tips": [
            "Implement 'Meta-Transactions' or gasless options to reduce user friction by 90%.",
            "Use 'Token-Gating' to create exclusive, high-value communities for your holders.",
        ],
        "schema_templates": {
            "problem": "Traditional digital commerce is plagued by high fees, slow settlements, and platform risk. Web3 offers a solution, but technical complexity prevents mass adoption.",
            "solution": "A hardened Web3 commerce stack that simplifies crypto payments, token-gated access, and decentralized delivery. Designed for the next generation of digital entrepreneurs.",
            "features": [
                "Multi-chain crypto payment gateway",
                "Automated token-gating & access control",
                "Non-custodial digital asset delivery",
                "Real-time blockchain event monitoring",
                "Gas-optimized smart contract templates"
            ]
        }
    },
    "default": {
        "mistakes": [
            "No gating logic: letting unpaid users access downloads via direct URLs.",
            "No support model: no FAQ, no troubleshooting, no refund/cancellation policy boundaries.",
            "Over-automating before you have a stable baseline and analytics instrumentation.",
        ],
        "expert_notes": [
            "Ship a stable baseline first, then iterate based on real user data.",
            "Focus on the 'Happy Path' first, but log all edge cases for future hardening.",
        ],
        "pro_tips": [
            "Include a 'Troubleshooting Matrix' to reduce common support queries by up to 40%.",
            "Test your checkout flow twice a week to ensure network-level stability.",
        ],
        "schema_templates": {
            "problem": "Creating and selling digital products is complex and time-consuming. Most creators fail due to technical friction and lack of a structured system.",
            "solution": "A professional-grade implementation system that handles everything from landing to delivery. Focus on your content, we handle the infrastructure.",
            "features": [
                "One-file deployment architecture",
                "Secure token-gated delivery",
                "Conversion-optimized landing components",
                "Built-in analytics & tracking",
                "Automated promotion asset generator"
            ]
        }
    }
}

def get_niche_for_topic(topic: str) -> str:
    """토픽 키워드를 기반으로 적절한 Niche 키를 반환합니다."""
    topic_lower = topic.lower()
    if any(k in topic_lower for k in ["web3", "blockchain", "nft", "dao", "token", "decentralized", "smart contract", "staking"]):
        return "web3"
    if any(k in topic_lower for k in ["finance", "crypto", "pay", "money", "wallet", "checkout", "trading", "tax"]):
        return "finance"
    elif any(k in topic_lower for k in ["productivity", "tool", "workflow", "save time", "automate", "system", "checklist", "management"]):
        return "productivity"
    elif any(k in topic_lower for k in ["marketing", "sale", "hook", "copy", "ad", "social", "traffic", "funnel", "viral"]):
        return "marketing"
    if any(k in topic_lower for k in ["ai", "automation", "bot", "agent", "prompt", "llm"]):
        return "ai_automation"
    if any(k in topic_lower for k in ["ecommerce", "shop", "store", "product", "merchant", "checkout", "cart"]):
        return "ecommerce"
    return "default"
