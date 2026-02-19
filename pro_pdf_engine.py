# -*- coding: utf-8 -*-
"""
pro_pdf_engine.py

목적(운영용):
- outputs/<product_id>/product*.md 를 "상업 판매 가능한 수준"의 PDF로 변환한다.
- reportlab(platypus) 기반: 표지/TOC/헤더/푸터/콜아웃/코드블록/표/리스트를 안전하게 지원한다.
- 완전한 Markdown 파서는 아니고, 실전 자동화에 필요한 subset을 "절대 크래시 없이" 처리한다.

지원(보수적 subset):
- Heading: #, ##, ### (H1/H2/H3)
- Bullet list: - , *
- Ordered list: 1) , 1.
- Blockquote: > ...
- Fenced code: ``` ... ```
- Table: |a|b| 형태

주의:
- PDF 생성 실패 시 ok=False 반환하고 error 메시지를 남긴다(파이프라인 크래시 금지).
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# -----------------------------
# Types
# -----------------------------


@dataclass
class PDFBuildResult:
    ok: bool
    pdf_path: Path
    error: Optional[str] = None


# -----------------------------
# Regex
# -----------------------------

RE_H = re.compile(r"^(#{1,3})\s+(.*)$")
RE_BULLET = re.compile(r"^\s*[-*]\s+(.*)$")
RE_OL_1 = re.compile(r"^\s*(\d+)\)\s+(.*)$")
RE_OL_2 = re.compile(r"^\s*(\d+)\.\s+(.*)$")
RE_TABLE_LINE = re.compile(r"^\|.*\|\s*$")
RE_BLOCKQUOTE = re.compile(r"^\s*>\s?(.*)$")


# -----------------------------
# Helpers
# -----------------------------


def _escape(s: str) -> str:
    """Paragraph XML 안전 이스케이프."""
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _header_footer(canvas, doc, title: str):
    """상단 제목 + 하단 페이지 번호."""
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.grey)
    canvas.drawString(30, A4[1] - 30, (title or "")[:90])
    canvas.drawRightString(A4[0] - 30, 20, f"Page {doc.page}")
    canvas.restoreState()


def _parse_markdown_tables(lines: List[str]) -> Dict[int, Tuple[int, List[List[str]]]]:
    """테이블 블록을 찾아 start_line -> (end_line, rows) 형태로 반환한다."""
    table_starts: Dict[int, Tuple[int, List[List[str]]]] = {}
    i = 0
    while i < len(lines):
        if RE_TABLE_LINE.match(lines[i].strip()):
            start = i
            buf: List[str] = []
            while i < len(lines) and RE_TABLE_LINE.match(lines[i].strip()):
                buf.append(lines[i].strip())
                i += 1

            rows: List[List[str]] = []
            for ln in buf:
                # 헤더 구분선(----) 제거
                if re.match(r"^\|\s*[-: ]+\|\s*[-: ]+\|", ln):
                    continue
                cells = [c.strip() for c in ln.strip("|").split("|")]
                rows.append(cells)

            if rows:
                table_starts[start] = (i, rows)
        else:
            i += 1
    return table_starts


def _build_cover(story: List, styles, meta: Dict[str, str]) -> None:
    """표지(커버) 페이지."""
    story.append(Spacer(1, 90))
    story.append(
        Paragraph(_escape(meta.get("brand", "MetaPassiveIncome")), styles["Title"])
    )
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            _escape(meta.get("title", "Premium Digital Product")), styles["Heading1"]
        )
    )
    story.append(Spacer(1, 10))
    if meta.get("subtitle"):
        story.append(Paragraph(_escape(meta["subtitle"]), styles["Normal"]))
        story.append(Spacer(1, 16))

    info_lines = [
        f"Product ID: {meta.get('product_id','')}",
        f"Language: {meta.get('language','')}",
        f"Generated: {meta.get('generated_at','')}",
        f"Version: {meta.get('version','v1')}",
    ]
    if meta.get("price"):
        info_lines.append(f"Suggested Price: {meta['price']}")
    story.append(Spacer(1, 18))
    for ln in info_lines:
        story.append(Paragraph(_escape(ln), styles["Normal"]))
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 28))
    story.append(
        Paragraph(
            _escape(
                meta.get(
                    "footer_note", "Operational playbook + templates + promotion assets"
                )
            ),
            styles["Italic"],
        )
    )
    story.append(PageBreak())


def _build_toc(story: List, styles, headings: List[str]) -> None:
    """간단 TOC(헤딩 텍스트 목록)."""
    story.append(Paragraph("Table of Contents", styles["Heading1"]))
    story.append(Spacer(1, 8))
    for h in headings[:80]:
        story.append(Paragraph("• " + _escape(h), styles["Normal"]))
        story.append(Spacer(1, 2))
    story.append(PageBreak())


def build_pdf_from_markdown(
    md_path: Path,
    pdf_path: Path,
    title: str,
    *,
    cover_meta: Optional[Dict[str, str]] = None,
) -> PDFBuildResult:
#     """
#     md_path를 읽어 pdf_path로 PDF를 생성한다.
# 
#     cover_meta(선택):
#       - brand, title, subtitle, product_id, language, generated_at, version, price, footer_note
#     """
    try:
        md = md_path.read_text(encoding="utf-8", errors="ignore")
        lines = md.splitlines()

        styles = getSampleStyleSheet()

        # 스타일 강화(상업용 느낌)
        styles.add(
            ParagraphStyle(
                name="Body", parent=styles["Normal"], fontSize=10.2, leading=14
            )
        )
        styles.add(
            ParagraphStyle(
                name="Small",
                parent=styles["Normal"],
                fontSize=9,
                leading=12,
                textColor=colors.grey,
            )
        )
        styles.add(
            ParagraphStyle(
                name="Quote",
                parent=styles["Normal"],
                fontSize=10,
                leading=14,
                leftIndent=14,
                textColor=colors.HexColor("#333333"),
            )
        )
        try:
            styles.add(
                ParagraphStyle(
                    name="Code",
                    parent=styles["Normal"],
                    fontName="Courier",
                    fontSize=9,
                    leading=11,
                    backColor=colors.whitesmoke,
                    leftIndent=10,
                    rightIndent=10,
                    spaceBefore=6,
                    spaceAfter=6,
                )
            )
        except KeyError:
            code_style = styles["Code"]
            code_style.fontName = "Courier"
            code_style.fontSize = 9
            code_style.leading = 11
            code_style.backColor = colors.whitesmoke
            code_style.leftIndent = 10
            code_style.rightIndent = 10
            code_style.spaceBefore = 6
            code_style.spaceAfter = 6
        styles.add(
            ParagraphStyle(
                name="H1", parent=styles["Heading1"], spaceBefore=14, spaceAfter=10
            )
        )
        styles.add(
            ParagraphStyle(
                name="H2", parent=styles["Heading2"], spaceBefore=12, spaceAfter=8
            )
        )
        styles.add(
            ParagraphStyle(
                name="H3", parent=styles["Heading3"], spaceBefore=10, spaceAfter=6
            )
        )

        story: List = []

        # 커버/TOC
        meta = dict(cover_meta or {})
        meta.setdefault("brand", "MetaPassiveIncome")
        meta.setdefault("title", title or "Premium Digital Product")
        meta.setdefault("generated_at", time.strftime("%Y-%m-%d", time.gmtime()))
        _build_cover(story, styles, meta)

        headings: List[str] = []
        for ln in lines:
            m = RE_H.match(ln.strip())
            if m and len(m.group(1)) <= 2:
                headings.append(m.group(2).strip())
        _build_toc(story, styles, headings)

        # 테이블 위치 인덱스
        table_starts = _parse_markdown_tables(lines)

        in_code = False
        code_buf: List[str] = []

        def flush_code():
            nonlocal code_buf
            if code_buf:
                code_text = "\n".join(code_buf).rstrip("\n")
                story.append(
                    Paragraph(_escape(code_text).replace("\n", "<br/>"), styles["Code"])
                )
                story.append(Spacer(1, 6))
                code_buf = []

        i = 0
        while i < len(lines):
            # 테이블 블록 처리
            if i in table_starts and not in_code:
                end, rows = table_starts[i]
                # 컬럼 폭 자동(최대 6컬럼 정도를 가정)
                t = Table(rows, hAlign="LEFT")
                t.setStyle(
                    TableStyle(
                        [
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bdbdbd")),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f5f5f5")),
                            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, -1), 9),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 6),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                            ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ]
                    )
                )
                story.append(t)
                story.append(Spacer(1, 10))
                i = end
                continue

            ln = lines[i].rstrip("\n")

            # fenced code
            if ln.strip().startswith("```"):
                if in_code:
                    in_code = False
                    flush_code()
                else:
                    in_code = True
                i += 1
                continue

            if in_code:
                code_buf.append(ln)
                i += 1
                continue

            # headings
            m = RE_H.match(ln.strip())
            if m:
                level = len(m.group(1))
                text = m.group(2).strip()
                style = (
                    styles["H1"]
                    if level == 1
                    else styles["H2"] if level == 2 else styles["H3"]
                )
                story.append(Paragraph(_escape(text), style))
                story.append(Spacer(1, 4))
                i += 1
                continue

            # blank line
            if not ln.strip():
                story.append(Spacer(1, 6))
                i += 1
                continue

            # blockquote -> callout-ish
            qb = RE_BLOCKQUOTE.match(ln)
            if qb:
                qtext_lines = [qb.group(1)]
                j = i + 1
                while j < len(lines):
                    q2 = RE_BLOCKQUOTE.match(lines[j])
                    if not q2:
                        break
                    qtext_lines.append(q2.group(1))
                    j += 1
                qtxt = "\n".join([t for t in qtext_lines if t.strip()]).strip()
                if qtxt:
                    story.append(
                        KeepTogether(
                            [
                                Paragraph(
                                    _escape(qtxt).replace("\n", "<br/>"),
                                    styles["Quote"],
                                ),
                                Spacer(1, 8),
                            ]
                        )
                    )
                i = j
                continue

            # bullets (consecutive)
            b = RE_BULLET.match(ln)
            if b:
                bullets = [b.group(1).strip()]
                j = i + 1
                while j < len(lines):
                    m2 = RE_BULLET.match(lines[j])
                    if not m2:
                        break
                    bullets.append(m2.group(1).strip())
                    j += 1
                # render bullets as paragraphs with indent
                for item in bullets:
                    story.append(Paragraph("• " + _escape(item), styles["Body"]))
                    story.append(Spacer(1, 2))
                story.append(Spacer(1, 6))
                i = j
                continue

            # ordered list
            o1 = RE_OL_1.match(ln) or RE_OL_2.match(ln)
            if o1:
                items = [f"{o1.group(1)}. {o1.group(2).strip()}"]
                j = i + 1
                while j < len(lines):
                    m2 = RE_OL_1.match(lines[j]) or RE_OL_2.match(lines[j])
                    if not m2:
                        break
                    items.append(f"{m2.group(1)}. {m2.group(2).strip()}")
                    j += 1
                for it in items:
                    story.append(Paragraph(_escape(it), styles["Body"]))
                    story.append(Spacer(1, 2))
                story.append(Spacer(1, 6))
                i = j
                continue

            # normal paragraph
            story.append(Paragraph(_escape(ln), styles["Body"]))
            story.append(Spacer(1, 4))
            i += 1

        # finalize: flush remaining code (failsafe)
        if in_code:
            flush_code()

        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            rightMargin=36,
            leftMargin=36,
            topMargin=54,
            bottomMargin=44,
            title=title or "",
        )
        doc.build(
            story,
            onFirstPage=lambda c, d: _header_footer(c, d, title),
            onLaterPages=lambda c, d: _header_footer(c, d, title),
        )
        return PDFBuildResult(ok=True, pdf_path=pdf_path)
    except Exception as e:  # noqa: BLE001
        return PDFBuildResult(
            ok=False, pdf_path=pdf_path, error=f"{type(e).__name__}: {e}"
        )
