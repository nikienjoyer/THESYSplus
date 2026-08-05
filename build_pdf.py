#!/usr/bin/env python
"""Compile THESYSPLUS_EXPLAINED.md into a styled PDF.

Supports a small Markdown subset used by the explanations:
  # / ## / ###  headings
  - bullet items (one level)
  > blockquote
  ``` fenced code blocks ```
  --- horizontal rule
  **bold** and `inline code` inside paragraphs
"""
import re
import html
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Preformatted,
    ListFlowable, ListItem, HRFlowable, KeepTogether,
)

SRC = "THESYSPLUS_EXPLAINED.md"
OUT = "THESYSPLUS_EXPLAINED.pdf"

# ---- styles ---------------------------------------------------------------
ss = getSampleStyleSheet()
INK = colors.HexColor("#0b1020")
MUTED = colors.HexColor("#475569")
ACCENT = colors.HexColor("#1d4ed8")
CODE_BG = colors.HexColor("#f1f5f9")
SOFT = colors.HexColor("#e2e8f0")

styles = {
    "h1": ParagraphStyle("h1", parent=ss["Title"], fontSize=22, leading=27,
                         textColor=INK, spaceAfter=6, spaceBefore=4),
    "h2": ParagraphStyle("h2", parent=ss["Heading2"], fontSize=14.5, leading=18,
                         textColor=ACCENT, spaceBefore=14, spaceAfter=6),
    "h3": ParagraphStyle("h3", parent=ss["Heading3"], fontSize=12, leading=15,
                         textColor=INK, spaceBefore=8, spaceAfter=3),
    "body": ParagraphStyle("body", parent=ss["BodyText"], fontSize=10, leading=14.5,
                           textColor=INK, spaceAfter=5, alignment=TA_LEFT,
                           leftIndent=2),
    "quote": ParagraphStyle("quote", parent=ss["BodyText"], fontSize=9.5, leading=13.5,
                            textColor=MUTED, leftIndent=12, rightIndent=8,
                            spaceBefore=3, spaceAfter=6, borderColor=SOFT,
                            borderWidth=0, backColor=colors.HexColor("#f8fafc")),
    "code": ParagraphStyle("code", parent=ss["Code"], fontSize=8.6, leading=11.5,
                           textColor=INK, backColor=CODE_BG, borderColor=SOFT,
                           borderWidth=0.5, borderPadding=5, leftIndent=4,
                           rightIndent=4, spaceBefore=3, spaceAfter=6),
}

# ---- inline formatting ----------------------------------------------------
def inline(text: str) -> str:
    """Escape then apply **bold** and `code` to reportlab markup."""
    text = html.escape(text, quote=False)
    # code spans first (so inner ** are not touched)
    text = re.sub(r"`([^`]+)`",
                  lambda m: "<font face='Courier'>%s</font>" % m.group(1), text)
    # bold
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    return text

# ---- parser ---------------------------------------------------------------
def parse(md: str):
    lines = md.splitlines()
    flow = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]

        # fenced code block
        if line.strip().startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            code = "\n".join(buf).rstrip("\n")
            flow.append(Preformatted(code, styles["code"]))
            continue

        # horizontal rule
        if line.strip() == "---":
            flow.append(HRFlowable(width="100%", thickness=0.6,
                                   color=SOFT, spaceBefore=6, spaceAfter=8))
            i += 1
            continue

        # headings
        if line.startswith("### "):
            flow.append(Paragraph(inline(line[4:]), styles["h3"]))
            i += 1
            continue
        if line.startswith("## "):
            flow.append(Paragraph(inline(line[3:]), styles["h2"]))
            i += 1
            continue
        if line.startswith("# "):
            flow.append(Paragraph(inline(line[2:]), styles["h1"]))
            i += 1
            continue

        # blockquote (collect consecutive > lines)
        if line.lstrip().startswith(">"):
            buf = []
            while i < n and lines[i].lstrip().startswith(">"):
                buf.append(lines[i].lstrip()[1:].lstrip())
                i += 1
            txt = " ".join(buf)
            flow.append(Paragraph(inline(txt), styles["quote"]))
            continue

        # bullet list (collect consecutive - lines)
        if line.lstrip().startswith("- "):
            items = []
            while i < n and lines[i].lstrip().startswith("- "):
                items.append(Paragraph(inline(lines[i].lstrip()[2:]), styles["body"]))
                i += 1
            flow.append(ListFlowable(
                [ListItem(it, leftIndent=10, value="•") for it in items],
                bulletType="bullet", start="•", leftIndent=14,
            ))
            continue

        # blank line
        if not line.strip():
            i += 1
            continue

        # paragraph (collect consecutive non-special lines)
        buf = [line]
        i += 1
        while i < n and lines[i].strip() and not lines[i].startswith(("#", "- ", ">")) \
                and not lines[i].strip().startswith("```") and lines[i].strip() != "---":
            buf.append(lines[i])
            i += 1
        txt = " ".join(buf).strip()
        if txt:
            flow.append(Paragraph(inline(txt), styles["body"]))
    return flow

# ---- document with header/footer -----------------------------------------
def build():
    doc = BaseDocTemplate(
        OUT, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=16 * mm,
        title="THESYS+ Explained for a Child",
        author="THESYS+ explainer",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin,
                  doc.width, doc.height, id="main")

    def deco(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(doc.leftMargin, 10 * mm,
                          "THESYS+ — explained so a child can understand it")
        canvas.drawRightString(doc.width + doc.leftMargin, 10 * mm,
                               "Page %d" % d.page)
        canvas.setStrokeColor(SOFT)
        canvas.setLineWidth(0.5)
        canvas.line(doc.leftMargin, 13 * mm,
                    doc.width + doc.leftMargin, 13 * mm)
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=deco)])
    doc.build(parse(open(SRC, encoding="utf-8").read()))
    print("Wrote", OUT)

if __name__ == "__main__":
    build()
