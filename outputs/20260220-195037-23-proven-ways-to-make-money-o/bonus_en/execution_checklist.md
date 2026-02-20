# Execution Checklist (Premium)

## A) Ship v1 (Day 1–25)
- [ ] Define the offer outcome in 1 sentence
- [ ] Add proof blocks (diagram + case metric + asset count)
- [ ] Implement payment start/check/download with server-side gating
- [ ] Generate premium PDF + diagrams + bonus package + promotions
- [ ] Deploy bundle and run smoke test

## B) Instrumentation (Week 1–2)
- [ ] Track events: page_view, click_buy, pay_start, pay_success, download_success, support_click
- [ ] Record server-side: order_id, product_id, amount, currency, status timestamps
- [ ] Baseline targets:
  - LP→Checkout: ~3.6%
  - Checkout→Paid: ~42.0%
  - Paid→Download: ≥94.0%

## C) Support Boundaries (Week 2–3)
- [ ] Create FAQ and troubleshooting macros
- [ ] Define scope boundaries and refund policy
- [ ] Target support load: ≤3.5% per 100 sales

## D) Weekly Review (ongoing)
- [ ] Review funnel metrics
- [ ] Choose ONE experiment
- [ ] Ship change, measure impact, document learning
