# -*- coding: utf-8 -*-
"""
premium_pdf_builder.py

목적:
- reportlab "platypus"를 사용하여 프로급 PDF 레이아웃 생성
  (타이틀 페이지, TOC, 섹션 헤더, 콜아웃 박스, 이미지(다이어그램), 푸터)

입력:
- premium_content_engine.PremiumProduct
- diagram_generator.DiagramResult (PNG 경로 포함 가능)

출력:
- product.pdf

주의:
- reportlab 기본 폰트(Helvetica)를 사용한다(추가 폰트 설치 없이).
- SVG는 platypus Image로 직접 임베드되지 않으므로, PNG가 없으면 텍스트 대체.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

from diagram_generator import DiagramResult
from premium_content_engine import Callout, PremiumProduct


@dataclass(frozen=True)
class PDFBuildResult:
    ok: bool
    errors: List[str]


def _styles():
    """
    reportlab 기본 스타일시트에 "고유한 이름"으로 커스텀 스타일을 추가한다.
    (getSampleStyleSheet()에는 이미 'Bullet' 등 일부 이름이 존재할 수 있으므로 prefix 사용)
    """
    styles = getSampleStyleSheet()

    def add(style):
        # 중복 정의 방지: 이미 있으면 그대로 사용
        if style.name in styles.byName:
            return
        styles.add(style)

    add(
        ParagraphStyle(
            name="P_H1",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            spaceAfter=10,
        )
    )
    add(
        ParagraphStyle(
            name="P_H2",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            spaceBefore=10,
            spaceAfter=6,
        )
    )
    add(
        ParagraphStyle(
            name="P_Body",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10.8,
            leading=14.5,
            spaceAfter=8,
        )
    )
    add(
        ParagraphStyle(
            name="P_Small",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=12.5,
            textColor=colors.HexColor("#3b4452"),
            spaceAfter=6,
        )
    )
    add(
        ParagraphStyle(
            name="P_Bullet",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10.6,
            leading=14.0,
            leftIndent=14,
            bulletIndent=6,
            spaceAfter=4,
        )
    )
    add(
        ParagraphStyle(
            name="P_CalloutTitle",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13.5,
            spaceAfter=4,
        )
    )
    add(
        ParagraphStyle(
            name="P_CalloutBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10.2,
            leading=13.5,
            spaceAfter=0,
        )
    )
    return styles


def _footer(canvas, doc, footer_text: str) -> None:  # noqa: ANN001
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.HexColor("#667085"))
    canvas.drawString(18 * mm, 12 * mm, footer_text)
    canvas.drawRightString(195 * mm, 12 * mm, str(doc.page))
    canvas.restoreState()


def _render_table(table_spec: Dict[str, Any]) -> Table:
    """간단한 표 렌더링(TableSpec: headers, rows)."""
    headers = table_spec.get("headers", [])
    rows = table_spec.get("rows", [])
    data = []
    if headers:
        data.append(list(headers))
    for r in rows:
        data.append(list(r))
    t = Table(data, hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#121a24")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#e7eef7")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#2b3b52")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.HexColor("#0b1220"), colors.HexColor("#0b0f14")],
                ),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def _callout_box(callout: Callout, styles) -> Table:
    """
    콜아웃 박스(Expert Note / Pro Tip / Warning)를 테이블로 렌더링.
    """
    kind = (callout.kind or "").lower()
    label = {
        "expert_note": "EXPERT NOTE",
        "pro_tip": "PRO TIP",
        "warning": "WARNING",
    }.get(kind, kind.upper() or "NOTE")

    bg = {
        "expert_note": colors.HexColor("#F2F4F7"),
        "pro_tip": colors.HexColor("#ECFDF3"),
        "warning": colors.HexColor("#FFFAEB"),
    }.get(kind, colors.HexColor("#F2F4F7"))

    border = {
        "expert_note": colors.HexColor("#D0D5DD"),
        "pro_tip": colors.HexColor("#A6F4C5"),
        "warning": colors.HexColor("#FEDF89"),
    }.get(kind, colors.HexColor("#D0D5DD"))

    title = Paragraph(f"{label}: {callout.title}", styles["P_CalloutTitle"])
    body = Paragraph(callout.body.replace("\n", "<br/>"), styles["P_CalloutBody"])

    t = Table([[title], [body]], colWidths=[170 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), bg),
                ("BOX", (0, 0), (-1, -1), 1, border),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return t


def _safe_img(path: Path, width_mm: float) -> Optional[Image]:
    """
    이미지 로드(실패하면 None).
    """
    try:
        if not path.exists() or path.stat().st_size <= 0:
            return None
        img = Image(str(path))
        img.drawWidth = width_mm * mm
        # keep aspect ratio
        ratio = img.imageHeight / float(img.imageWidth)
        img.drawHeight = img.drawWidth * ratio
        return img
    except Exception:  # noqa: BLE001
        return None


def build_premium_pdf(
    pdf_path: Path,
    product: PremiumProduct,
    diagrams: Optional[DiagramResult] = None,
) -> PDFBuildResult:
#     """
#     PREMIUM PDF 생성.
#     """
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    errors: List[str] = []

    styles = _styles()

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=product.title,
        author="MetaPassiveIncome Product Factory",
    )

    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            name="TOC1",
            fontName="Helvetica",
            fontSize=11,
            leftIndent=10,
            firstLineIndent=-10,
            spaceAfter=6,
        ),
        ParagraphStyle(
            name="TOC2",
            fontName="Helvetica",
            fontSize=10,
            leftIndent=22,
            firstLineIndent=-10,
            spaceAfter=4,
        ),
    ]

    story: List[Any] = []

    # --- Title page ---
    story.append(Spacer(1, 16 * mm))
    story.append(Paragraph(product.title, styles["P_H1"]))
    story.append(Paragraph(product.subtitle, styles["P_Body"]))
    story.append(Spacer(1, 6 * mm))
    story.append(
        Paragraph(f"<b>product_id:</b> {product.product_id}", styles["P_Small"])
    )
    story.append(Paragraph(f"<b>topic:</b> {product.topic}", styles["P_Small"]))
    story.append(Paragraph(f"<b>audience:</b> {product.audience}", styles["P_Small"]))
    story.append(
        Paragraph(f"<b>perceived value:</b> {product.price_band}", styles["P_Small"])
    )
    story.append(Spacer(1, 10 * mm))

    # title page diagram (process_steps)
    if diagrams and diagrams.diagrams.get("process_steps"):
        img = _safe_img(diagrams.diagrams["process_steps"], width_mm=170)
        if img:
            story.append(Paragraph("System Overview Diagram", styles["P_H2"]))
            story.append(img)
            story.append(Spacer(1, 6 * mm))
        else:
            errors.append("Failed to load process_steps.png")
    story.append(PageBreak())

    # --- Table of contents ---
    story.append(Paragraph("Table of Contents", styles["P_H1"]))
    story.append(Spacer(1, 4 * mm))
    story.append(toc)
    story.append(PageBreak())

    # --- Diagrams page ---
    story.append(Paragraph("Key Diagrams", styles["P_H1"]))
    story.append(
        Paragraph(
            "These diagrams are included as quick-reference visuals.", styles["P_Body"]
        )
    )
    fig_no = 1
    for name, caption in [
        ("funnel_flow", "Funnel flow from landing to delivery"),
        ("system_architecture", "System architecture for payment + gating + delivery"),
        ("process_steps", "Implementation framework (step-by-step)"),
        ("payment_state_machine", "Payment state machine transitions"),
        ("delivery_gating", "Signed-token delivery gating"),
        ("support_triage", "Support triage workflow"),
        ("ab_test_loop", "A/B test loop (ship → measure → decide)"),
        ("promo_calendar_flow", "30-day promotion calendar flow"),
        ("troubleshooting_matrix", "Troubleshooting matrix overview"),
        ("optimization_cycle", "Weekly optimization cycle"),
    ]:
        if diagrams and diagrams.diagrams.get(name):
            img = _safe_img(diagrams.diagrams[name], width_mm=170)
            if img:
                story.append(Paragraph(f"Figure {fig_no}. {caption}", styles["P_H2"]))
                fig_no += 1
                story.append(img)
                story.append(Spacer(1, 6 * mm))
            else:
                errors.append(f"Failed to load {name}.png")
        else:
            # fallback text diagram note
            story.append(Paragraph(caption, styles["P_H2"]))
            story.append(
                Paragraph(
                    "Diagram asset unavailable on this environment. See assets/diagrams/*.svg for fallback.",
                    styles["P_Small"],
                )
            )
            story.append(Spacer(1, 6 * mm))
    story.append(PageBreak())

    # --- Content sections ---
    def add_heading(text: str, level: int) -> None:
        # level 1 -> Heading1, 2 -> Heading2
        style = styles["P_H1"] if level == 1 else styles["P_H2"]
        story.append(Paragraph(text, style))

    # For TOC: notify headings
    def _after_flowable(flowable):  # noqa: ANN001
        # Called by doc after each flowable is processed
        if isinstance(flowable, Paragraph):
            style_name = flowable.style.name
            if style_name == "P_H1":
                txt = flowable.getPlainText()
                key = txt
                doc.notify("TOCEntry", (0, txt, doc.page))
            elif style_name == "P_H2":
                txt = flowable.getPlainText()
                doc.notify("TOCEntry", (1, txt, doc.page))

    doc.afterFlowable = _after_flowable

    for sec in product.sections:
        add_heading(sec.title, 1)
        story.append(
            Paragraph(
                "This section contains structured, actionable content. Use checklists and callouts to execute.",
                styles["P_Small"],
            )
        )
        story.append(Spacer(1, 2 * mm))

        for sub in sec.subsections:
            # Keep heading + first paragraph together to avoid lonely headings
            block: List[Any] = []
            block.append(Paragraph(sub.title, styles["P_H2"]))
            if sub.paragraphs:
                block.append(Paragraph(sub.paragraphs[0], styles["P_Body"]))
            story.append(KeepTogether(block))

            # Remaining paragraphs
            for p in sub.paragraphs[1:]:
                story.append(Paragraph(p, styles["P_Body"]))

            # bullets
            for b in sub.bullets:
                story.append(
                    Paragraph(
                        b.replace("\n", "<br/>"), styles["P_Bullet"], bulletText="•"
                    )
                )

            # numbered steps (already like "1. ..." but we still style)
            for s in sub.numbered_steps:
                story.append(
                    Paragraph(
                        s.replace("\n", "<br/>"), styles["P_Bullet"], bulletText=""
                    )
                )

            # callouts
            for c in sub.callouts:
                story.append(Spacer(1, 2 * mm))
                story.append(_callout_box(c, styles))
                story.append(Spacer(1, 4 * mm))

            story.append(Spacer(1, 4 * mm))

        # --- Structured tables (premium) ---
        tables = (
            product.meta.get("tables", {}) if isinstance(product.meta, dict) else {}
        )
        if sec.key == "case_study" and isinstance(
            tables.get("case_before_after"), dict
        ):
            story.append(Paragraph("Before vs After (Table)", styles["P_H2"]))
            story.append(Spacer(1, 2 * mm))
            story.append(_render_table(tables["case_before_after"]))
            note = str(tables["case_before_after"].get("note") or "")
            if note:
                story.append(Spacer(1, 2 * mm))
                story.append(Paragraph(note, styles["P_Small"]))
            story.append(Spacer(1, 6 * mm))

        if sec.key == "troubleshooting" and isinstance(
            tables.get("troubleshooting_matrix"), dict
        ):
            story.append(Paragraph("Troubleshooting Matrix (Table)", styles["P_H2"]))
            story.append(Spacer(1, 2 * mm))
            story.append(_render_table(tables["troubleshooting_matrix"]))
            note = str(tables["troubleshooting_matrix"].get("note") or "")
            if note:
                story.append(Spacer(1, 2 * mm))
                story.append(Paragraph(note, styles["P_Small"]))
            story.append(Spacer(1, 6 * mm))

        story.append(PageBreak())

    footer_text = f"{product.title} — {product.product_id}"
    try:
        doc.build(
            story,
            onFirstPage=lambda canv, d: _footer(canv, d, footer_text),
            onLaterPages=lambda canv, d: _footer(canv, d, footer_text),
        )
        return PDFBuildResult(ok=(len(errors) == 0), errors=errors)
    except Exception as e:  # noqa: BLE001
        errors.append(f"{type(e).__name__}: {e}")
        return PDFBuildResult(ok=False, errors=errors)
