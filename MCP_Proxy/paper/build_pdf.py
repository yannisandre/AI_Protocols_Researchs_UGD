"""Build the illustrated manuscript with vector figures and audited result tables."""
import argparse
import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, CondPageBreak, KeepTogether

from diagrams import figures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().parent.parent / "output/pdf/MCP_Proxy_Research_Paper_Draft.pdf")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    for name, filename in [("D", "DejaVuSans.ttf"), ("D-Bold", "DejaVuSans-Bold.ttf"),
                           ("D-Italic", "DejaVuSans-Oblique.ttf"), ("D-Mono", "DejaVuSansMono.ttf")]:
        pdfmetrics.registerFont(TTFont(name, "/usr/share/fonts/truetype/dejavu/" + filename))
    pdfmetrics.registerFontFamily("D", normal="D", bold="D-Bold", italic="D-Italic")
    drawings = figures(root / "figures")
    navy = colors.HexColor("#15344D")
    styles = {
        "title": ParagraphStyle("title", fontName="D-Bold", fontSize=19, leading=24, textColor=navy, spaceAfter=7),
        "subtitle": ParagraphStyle("subtitle", fontName="D", fontSize=12, leading=17, textColor=navy, spaceAfter=13),
        "heading": ParagraphStyle("heading", fontName="D-Bold", fontSize=11.5, leading=16,
                                  textColor=navy, spaceBefore=12, spaceAfter=6, keepWithNext=True),
        "body": ParagraphStyle("body", fontName="D", fontSize=9.5, leading=14, spaceAfter=7,
                               allowWidows=0, allowOrphans=0),
        "note": ParagraphStyle("note", fontName="D", fontSize=8.3, leading=11.5,
                               textColor=colors.HexColor("#405767"), spaceBefore=3, spaceAfter=10),
        "cell": ParagraphStyle("cell", fontName="D", fontSize=7.5, leading=10),
        "caption": ParagraphStyle("caption", fontName="D", fontSize=8, leading=11,
                                  textColor=colors.HexColor("#405767"), spaceBefore=6, spaceAfter=12),
    }
    def markup(text):
        text = escape(text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
        text = re.sub(r"`(.+?)`", r'<font name="D-Mono" size="8.5">\1</font>', text)
        return re.sub(r"https://[^\s<]+", lambda m: '<link href="'+m[0]+'" color="#236692">'+m[0]+'</link>', text)
    story, paragraph, table_rows = [], [], []
    def flush_paragraph():
        if paragraph:
            text = " ".join(paragraph)
            kind = "note" if text.startswith("**AI assistance disclosure.**") else "body"
            story.append(Paragraph(markup(text), styles[kind]))
            paragraph.clear()
    def flush_table():
        if not table_rows:
            return
        rows = [[Paragraph(markup(c), styles["cell"]) for c in row] for row in table_rows]
        widths = ([112, 64, 36, 38, 80, 60, 58] if table_rows[0][0] == "Actor" else
                  [122, 45, 54, 43, 70, 62, 52] if table_rows[0][0] == "Model" else
                  [122, 59, 32, 43, 78, 40, 74])
        table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E9EFF4")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, navy),
            ("LINEBELOW", (0, -1), (-1, -1), 0.4, colors.HexColor("#C4CFD8")),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.extend([CondPageBreak(160), table, Spacer(1, 10)])
        table_rows.clear()
    for raw in (root / "paper_draft.md").read_text().splitlines() + [""]:
        line = raw.strip()
        if line.startswith("|"):
            flush_paragraph()
            cells = [c.strip() for c in line.strip("|").split("|")]
            if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                table_rows.append(cells)
            continue
        flush_table()
        figure = re.fullmatch(r"!\[(.+)\]\(figures/([a-z_]+)\.svg\)", line)
        if figure:
            flush_paragraph()
            caption, name = figure.groups()
            story.append(KeepTogether([Spacer(1, 6), drawings[name],
                                       Paragraph(markup(caption), styles["caption"])]))
        elif not line:
            flush_paragraph()
        elif line.startswith("#"):
            flush_paragraph()
            level = len(line) - len(line.lstrip("#"))
            kind = "title" if level == 1 else "subtitle" if level == 2 else "heading"
            story.append(Paragraph(markup(line.lstrip("# ")), styles[kind]))
        else:
            paragraph.append(line)
    def page(canvas, doc):
        canvas.setStrokeColor(colors.HexColor("#CFD8E0")); canvas.line(46, 39, A4[0]-46, 39)
        canvas.setFont("D", 7); canvas.setFillColor(colors.HexColor("#526575"))
        canvas.drawString(46, 25, "Yannis ANDRE | MCP boundary security")
        canvas.drawRightString(A4[0]-46, 25, str(doc.page))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(str(args.output), pagesize=A4, leftMargin=46, rightMargin=46,
                      topMargin=40, bottomMargin=54, title="Task Authorization, Export Guards and Bounded Recovery at the MCP Boundary",
                      author="Yannis ANDRE").build(story, onFirstPage=page, onLaterPages=page)
    print(args.output)


if __name__ == "__main__":
    main()
