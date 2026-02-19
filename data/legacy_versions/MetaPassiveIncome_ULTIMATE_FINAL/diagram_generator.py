# -*- coding: utf-8 -*-
"""
diagram_generator.py (PREMIUM+)

목적:
- 프리미엄 제품 PDF에 포함될 "간단하지만 유료 제품처럼 보이는" 다이어그램 PNG를 자동 생성한다.
- 저장 위치: outputs/<product_id>/assets/diagrams/

핵심:
- reportlab.graphics + renderPM 으로 PNG 생성(추가 의존성 최소화)
- renderPM 실패 환경 대비: SVG placeholder도 함께 생성

생성 다이어그램(기본 10종):
1) funnel_flow.png
2) system_architecture.png
3) process_steps.png
4) payment_state_machine.png
5) delivery_gating.png
6) support_triage.png
7) ab_test_loop.png
8) promo_calendar_flow.png
9) troubleshooting_matrix.png
10) optimization_cycle.png
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

from reportlab.graphics import renderPM
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors


@dataclass(frozen=True)
class DiagramResult:
    ok: bool
    diagrams: Dict[str, Path]  # name -> png path (preferred)
    fallbacks_svg: Dict[str, Path]  # name -> svg path (if png failed)
    errors: List[str]


# ----------------------------
# Low-level helpers
# ----------------------------


def _safe_mkdir(p: Path) -> None:
    """디렉토리 생성(이미 있으면 통과)."""
    p.mkdir(parents=True, exist_ok=True)


def _try_png(d: Drawing, out_path: Path) -> Tuple[bool, str]:
    """renderPM으로 PNG 저장 시도."""
    try:
        renderPM.drawToFile(d, str(out_path), fmt="PNG")
        if out_path.exists() and out_path.stat().st_size > 0:
            return True, ""
        return False, "renderPM produced empty file"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


def _write_svg_placeholder(svg_path: Path, title: str, lines: List[str]) -> None:
    """PNG 실패 시 SVG 텍스트 placeholder 생성."""
    w = 900
    h = 520
    safe_title = (title or "diagram").replace("&", "and")
    body = "\n".join(lines)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">
  <rect x="0" y="0" width="{w}" height="{h}" fill="#0b0f14"/>
  <text x="24" y="56" font-size="28" font-family="Arial" fill="#e7eef7">{safe_title}</text>
  <text x="24" y="96" font-size="16" font-family="Arial" fill="#93a4b8">PNG generation failed. This is a fallback SVG placeholder.</text>
  <text x="24" y="140" font-size="16" font-family="Courier New" fill="#e7eef7">{body.replace("<","&lt;").replace(">","&gt;")}</text>
</svg>
# """
#     svg_path.write_text(svg, encoding="utf-8")
# 
# 
# def _box(d: Drawing, x: int, y: int, w: int, h: int, title: str) -> None:
#     """박스 + 타이틀."""
    d.add(
        Rect(
            x,
            y,
            w,
            h,
            strokeColor=colors.HexColor("#2b3b52"),
            fillColor=colors.HexColor("#121a24"),
            strokeWidth=2,
        )
    )
    d.add(
        String(
            x + 10,
            y + h - 24,
            title,
            fontName="Helvetica-Bold",
            fontSize=12,
            fillColor=colors.HexColor("#e7eef7"),
        )
    )


def _label(d: Drawing, x: int, y: int, text: str) -> None:
    """작은 라벨."""
    d.add(
        String(
            x,
            y,
            text,
            fontName="Helvetica",
            fontSize=10,
            fillColor=colors.HexColor("#93a4b8"),
        )
    )


def _arrow(d: Drawing, x1: int, y1: int, x2: int, y2: int) -> None:
    """직선 화살표(간단 삼각형 헤드)."""
    d.add(Line(x1, y1, x2, y2, strokeColor=colors.HexColor("#7dd3fc"), strokeWidth=2))
    # very simple head
    hx = x2
    hy = y2
    d.add(
        Line(
            hx,
            hy,
            hx - 6,
            hy - 4,
            strokeColor=colors.HexColor("#7dd3fc"),
            strokeWidth=2,
        )
    )
    d.add(
        Line(
            hx,
            hy,
            hx - 6,
            hy + 4,
            strokeColor=colors.HexColor("#7dd3fc"),
            strokeWidth=2,
        )
    )


# ----------------------------
# Diagram builders
# ----------------------------


def _diagram_funnel_flow() -> Drawing:
    d = Drawing(900, 520)
    _label(d, 24, 490, "Funnel flow — trust → payment → delivery")
    _box(d, 60, 340, 180, 120, "Landing page")
    _label(d, 70, 380, "proof blocks + FAQ")
    _box(d, 320, 340, 180, 120, "Start payment")
    _label(d, 330, 380, "POST /api/pay/start")
    _box(d, 580, 340, 200, 120, "Invoice / wallet")
    _label(d, 590, 380, "provider checkout")
    _box(d, 320, 140, 180, 120, "Check status")
    _label(d, 330, 180, "GET /api/pay/check")
    _box(d, 580, 140, 200, 120, "Gated download")
    _label(d, 590, 180, "signed token")
    _arrow(d, 240, 400, 320, 400)
    _arrow(d, 500, 400, 580, 400)
    _arrow(d, 680, 340, 430, 260)
    _arrow(d, 500, 200, 580, 200)
    return d


def _diagram_system_architecture() -> Drawing:
    d = Drawing(900, 520)
    _label(d, 24, 490, "System architecture — minimal but production-shaped")
    _box(d, 60, 330, 200, 140, "Client")
    _label(d, 70, 370, "landing + status UI")
    _box(d, 320, 330, 220, 140, "API / Serverless")
    _label(d, 330, 390, "/api/pay/*")
    _label(d, 330, 370, "state machine")
    _box(d, 600, 330, 240, 140, "Payment Provider")
    _label(d, 610, 390, "NOWPayments")
    _box(d, 320, 130, 220, 140, "Order Store")
    _label(d, 330, 190, "file / Upstash")
    _box(d, 600, 130, 240, 140, "Delivery")
    _label(d, 610, 190, "PDF + bundle zip")
    _label(d, 610, 170, "signed tokens")
    _arrow(d, 260, 400, 320, 400)
    _arrow(d, 540, 400, 600, 400)
    _arrow(d, 430, 330, 430, 270)
    _arrow(d, 540, 200, 600, 200)
    _arrow(d, 430, 270, 600, 200)
    return d


def _diagram_process_steps() -> Drawing:
    d = Drawing(900, 520)
    _label(d, 24, 490, "Implementation framework — step-by-step")
    steps = [
        ("Step 1", "Define offer + promise"),
        ("Step 2", "Build proof blocks"),
        ("Step 3", "Integrate crypto checkout"),
        ("Step 4", "Gate delivery + support"),
        ("Step 5", "Launch + measure"),
        ("Step 6", "Optimize + scale"),
    ]
    x = 60
    y = 340
    for i, (s, t) in enumerate(steps):
        _box(d, x + i * 130, y, 120, 120, s)
        _label(d, x + i * 130 + 10, y + 60, t)
        if i < len(steps) - 1:
            _arrow(d, x + i * 130 + 120, y + 60, x + (i + 1) * 130, y + 60)
    return d


def _diagram_payment_state_machine() -> Drawing:
    d = Drawing(900, 520)
    _label(d, 24, 490, "Payment state machine — deterministic transitions")
    states = ["initiated", "pending", "paid", "delivered", "expired/refunded"]
    x0 = 60
    y0 = 320
    w = 150
    h = 90
    for i, st in enumerate(states):
        _box(d, x0 + i * 160, y0, w, h, st)
        if i < len(states) - 1:
            _arrow(d, x0 + i * 160 + w, y0 + 45, x0 + (i + 1) * 160, y0 + 45)
    _label(
        d,
        60,
        260,
        "Rules: paid ⇒ issue signed download token; download ⇒ delivered; timeouts ⇒ expired.",
    )
    return d


def _diagram_delivery_gating() -> Drawing:
    d = Drawing(900, 520)
    _label(d, 24, 490, "Delivery gating — prevent link sharing")
    _box(d, 60, 320, 220, 120, "Order paid?")
    _box(d, 330, 320, 240, 120, "Issue token")
    _label(d, 340, 360, "HMAC(order_id, exp)")
    _box(d, 620, 320, 220, 120, "Download")
    _label(d, 630, 360, "token validated")
    _arrow(d, 280, 380, 330, 380)
    _arrow(d, 570, 380, 620, 380)
    _box(d, 330, 150, 240, 110, "Invalid/expired")
    _label(d, 340, 200, "403 + retry flow")
    _arrow(d, 400, 320, 400, 260)
    return d


def _diagram_support_triage() -> Drawing:
    d = Drawing(900, 520)
    _label(d, 24, 490, "Support triage — reduce tickets")
    _box(d, 60, 340, 240, 120, "Incoming issue")
    _box(d, 340, 340, 240, 120, "Classify")
    _label(d, 350, 390, "payment / delivery / network")
    _box(d, 620, 340, 240, 120, "Macro response")
    _label(d, 630, 390, "copy-paste templates")
    _box(d, 340, 160, 240, 120, "Escalate")
    _label(d, 350, 210, "only hard cases")
    _arrow(d, 300, 400, 340, 400)
    _arrow(d, 580, 400, 620, 400)
    _arrow(d, 460, 340, 460, 280)
    return d


def _diagram_ab_test_loop() -> Drawing:
    d = Drawing(900, 520)
    _label(d, 24, 490, "A/B test loop — ship → measure → decide")
    _box(d, 80, 340, 220, 120, "Variant A/B")
    _box(d, 350, 340, 220, 120, "Measure")
    _label(d, 360, 390, "conv + completion")
    _box(d, 620, 340, 220, 120, "Decide")
    _label(d, 630, 390, "keep + iterate")
    _arrow(d, 300, 400, 350, 400)
    _arrow(d, 570, 400, 620, 400)
    _arrow(d, 730, 340, 190, 280)
    return d


def _diagram_promo_calendar_flow() -> Drawing:
    d = Drawing(900, 520)
    _label(d, 24, 490, "Promotion calendar — 30-day content machine")
    _box(d, 80, 340, 220, 120, "Daily topics")
    _label(d, 90, 390, "hooks + CTA")
    _box(d, 350, 340, 220, 120, "Channel adapt")
    _label(d, 360, 390, "X / Shorts / Blog")
    _box(d, 620, 340, 220, 120, "Publish")
    _label(d, 630, 390, "scheduled drops")
    _arrow(d, 300, 400, 350, 400)
    _arrow(d, 570, 400, 620, 400)
    return d


def _diagram_troubleshooting_matrix() -> Drawing:
    d = Drawing(900, 520)
    _label(d, 24, 490, "Troubleshooting matrix — symptoms → causes → fixes")
    _box(d, 60, 300, 260, 160, "Symptom")
    _label(d, 70, 420, "Payment stuck pending")
    _label(d, 70, 400, "Wrong network")
    _label(d, 70, 380, "Download blocked")
    _box(d, 340, 300, 260, 160, "Cause")
    _label(d, 350, 420, "Confirmations / fees")
    _label(d, 350, 400, "User confusion")
    _label(d, 350, 380, "Expired token")
    _box(d, 620, 300, 240, 160, "Fix")
    _label(d, 630, 420, "Show status + ETA")
    _label(d, 630, 400, "Add FAQ + guardrails")
    _label(d, 630, 380, "Re-issue token")
    _arrow(d, 320, 380, 340, 380)
    _arrow(d, 600, 380, 620, 380)
    return d


def _diagram_optimization_cycle() -> Drawing:
    d = Drawing(900, 520)
    _label(d, 24, 490, "Optimization cycle — weekly compounding")
    _box(d, 120, 340, 200, 120, "Collect metrics")
    _box(d, 380, 340, 200, 120, "Find top 3 leaks")
    _box(d, 640, 340, 200, 120, "Ship fixes")
    _arrow(d, 320, 400, 380, 400)
    _arrow(d, 580, 400, 640, 400)
    _arrow(d, 740, 340, 220, 280)
    _label(d, 160, 280, "repeat weekly")
    return d


_DIAGRAM_BUILDERS = {
    "funnel_flow": _diagram_funnel_flow,
    "system_architecture": _diagram_system_architecture,
    "process_steps": _diagram_process_steps,
    "payment_state_machine": _diagram_payment_state_machine,
    "delivery_gating": _diagram_delivery_gating,
    "support_triage": _diagram_support_triage,
    "ab_test_loop": _diagram_ab_test_loop,
    "promo_calendar_flow": _diagram_promo_calendar_flow,
    "troubleshooting_matrix": _diagram_troubleshooting_matrix,
    "optimization_cycle": _diagram_optimization_cycle,
}


# ----------------------------
# Public API
# ----------------------------


def generate_diagrams(
    output_dir: Path, product_id: str, meta: Dict[str, Any] | None = None
) -> DiagramResult:
#     """
#     outputs/<product_id>/assets/diagrams/ 아래에 다이어그램 생성.
# 
#     반환:
#     - diagrams: name->png path
#     - fallbacks_svg: name->svg path (png 실패한 것만)
#     - errors: 실패 사유 목록
#     """
    diagrams_dir = output_dir / product_id / "assets" / "diagrams"
    _safe_mkdir(diagrams_dir)

    diagrams: Dict[str, Path] = {}
    fallbacks: Dict[str, Path] = {}
    errors: List[str] = []

    for name, builder in _DIAGRAM_BUILDERS.items():
        png_path = diagrams_dir / f"{name}.png"
        svg_path = diagrams_dir / f"{name}.svg"

        drawing = builder()

        ok, err = _try_png(drawing, png_path)
        if ok:
            diagrams[name] = png_path
            continue

        # PNG 실패: SVG 생성 + 오류 기록
        _write_svg_placeholder(
            svg_path,
            title=name,
            lines=[
                f"{name}",
                "This diagram could not be rendered to PNG in this environment.",
                "Use the PDF text diagram fallback or install renderPM dependencies.",
            ],
        )
        fallbacks[name] = svg_path
        errors.append(f"{name}: {err}")

    return DiagramResult(
        ok=(len(diagrams) > 0),
        diagrams=diagrams,
        fallbacks_svg=fallbacks,
        errors=errors,
    )
