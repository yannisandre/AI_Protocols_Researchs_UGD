"""Vector figures for the manuscript, generated from the documented lab design.

The drawings are embedded directly in the PDF and exported as SVG for Markdown.
No experiment is started and no provider API is contacted.
"""
from pathlib import Path

from reportlab.graphics import renderSVG
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors

WIDTH = 503
NAVY = colors.HexColor("#15344D")
INK = colors.HexColor("#294253")
MUTED = colors.HexColor("#536879")
BLUE = colors.HexColor("#EDF4F9")
GREEN = colors.HexColor("#EDF5F1")
PURPLE = colors.HexColor("#F2EFF8")
AMBER = colors.HexColor("#FFF4E7")
WHITE = colors.white
STROKE = colors.HexColor("#9EAFBC")


def label(d, x, y, text, size=8, color=INK, bold=False, anchor="start"):
    d.add(String(x, y, text, fontName="D-Bold" if bold else "D",
                 fontSize=size, fillColor=color, textAnchor=anchor))


def box(d, x, y, w, h, title, lines=(), fill=BLUE, title_size=9, body_size=8):
    d.add(Rect(x, y, w, h, rx=5, ry=5, fillColor=fill, strokeColor=STROKE, strokeWidth=.7))
    label(d, x + 10, y + h - 17, title, title_size, NAVY, True)
    for i, text in enumerate(lines):
        label(d, x + 10, y + h - 32 - i * 11, text, body_size)


def arrow(d, points, color=NAVY, dashed=False):
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        line = Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=.95)
        if dashed:
            line.strokeDashArray = [3, 2]
        d.add(line)
    (x1, y1), (x2, y2) = points[-2:]
    dx, dy = x2-x1, y2-y1
    length = (dx*dx + dy*dy) ** .5
    ux, uy = dx/length, dy/length
    d.add(Polygon([x2, y2, x2-5*ux+2.3*uy, y2-5*uy-2.3*ux,
                   x2-5*ux-2.3*uy, y2-5*uy+2.3*ux],
                  fillColor=color, strokeColor=color, strokeWidth=.3))


def architecture():
    d = Drawing(WIDTH, 310)
    d.add(Rect(0, 9, WIDTH, 222, rx=7, ry=7, fillColor=colors.HexColor("#FAFBFC"),
               strokeColor=STROKE, strokeWidth=.8))
    label(d, 12, 214, "ONE PC / FOUR DOCKER CONTAINERS", 8, MUTED, True)
    box(d, 340, 253, 163, 55, "External provider APIs",
        ["Actor + separate no-tools judge", "Trusted inference processors"], PURPLE, body_size=7.4)
    box(d, 15, 120, 135, 78, "1  Agent / MCP client",
        ["Python orchestration", "Conversation in memory", "Host control credential"])
    box(d, 214, 120, 135, 78, "2  Security proxy",
        ["Task policy + guards", "Observed calls / documents", "Only provider egress"])
    box(d, 214, 23, 135, 76, "3  MCP SDK server",
        ["A/B fixtures (read-only)", "Read, draft, send tools", "Independent effect logs"], GREEN)
    box(d, 383, 23, 120, 76, "4  Mock collector",
        ["Separate export sink", "Received report content", "Independent receipt logs"], GREEN, body_size=7.6)
    arrow(d, [(150, 157), (214, 157)])
    label(d, 182, 171, "MCP", 7.6, anchor="middle")
    label(d, 182, 161, "HTTPS", 7.1, anchor="middle")
    arrow(d, [(150, 184), (172, 184), (172, 205), (281, 205), (281, 198)], dashed=True)
    label(d, 204, 209, "Control + model relay", 7, MUTED)
    arrow(d, [(330, 198), (330, 280), (340, 280)])
    label(d, 322, 242, "HTTPS", 7.2, MUTED, anchor="end")
    arrow(d, [(281, 120), (281, 99)])
    label(d, 273, 108, "MCP / HTTPS", 7.1, anchor="end")
    arrow(d, [(349, 60), (383, 60)])
    label(d, 366, 76, "HTTPS", 6.9, anchor="middle")
    label(d, 15, 87, "Agent cannot directly reach", 7.4, MUTED)
    label(d, 15, 76, "server, collector or Internet.", 7.4, MUTED)
    label(d, 15, 52, "Dashed: application-specific", 7.1, MUTED)
    label(d, 15, 41, "HTTPS routes, separate from MCP.", 7.1, MUTED)
    return d


def hybrid_recovery():
    d = Drawing(WIDTH, 295)
    label(d, 0, 283, "HYBRID CONTROL BEFORE AN EXPORT", 8, MUTED, True)
    box(d, 0, 224, 280, 43, "Candidate send_report", ["Tool arguments chosen by the acting model"])
    box(d, 0, 170, 280, 43, "Resource / destination checks", ["Validate schema and task permissions"])
    box(d, 0, 116, 280, 43, "Deterministic private-field check (DLP)", ["A known forbidden match is a final refusal"])
    box(d, 0, 62, 280, 43, "Separate LLM judge", ["Evaluate goal, sources, workflow and candidate"], PURPLE)
    box(d, 0, 8, 280, 43, "Forward to the MCP server", ["Only after all required checks permit the call"], GREEN)
    for top in (224, 170, 116, 62):
        arrow(d, [(140, top), (140, top-11)])
    label(d, 148, 107, "no known match", 6.8, MUTED)
    label(d, 148, 53, "allow", 6.8, MUTED)
    box(d, 325, 116, 178, 85, "Content refusal",
        ["The proposed send is blocked.", "If enabled and still available:", "one trusted-host correction.", "No new permission is granted."], AMBER, body_size=7.7)
    arrow(d, [(280, 138), (325, 138)])
    label(d, 302, 145, "deny", 6.8, anchor="middle")
    arrow(d, [(280, 83), (301, 83), (301, 126), (325, 126)])
    label(d, 303, 72, "deny / uncertain", 6.8)
    arrow(d, [(414, 201), (414, 245), (280, 245)], dashed=True)
    label(d, 329, 253, "Revised candidate", 7.4, MUTED)
    label(d, 330, 221, "Same checks apply again", 7.3, MUTED)
    box(d, 325, 8, 178, 54, "Failures remain distinct",
        ["Resource denial: block.", "Invalid judge: no host recovery."], fill=colors.HexColor("#F3F5F7"), body_size=7.3)
    return d


def evaluation_design():
    d = Drawing(WIDTH, 247)
    label(d, 0, 235, "FIVE FIXED CASES", 8, MUTED, True)
    cases = [("Public", ["Plain summary", "No injection"], BLUE),
             ("Public metadata", ["Benign fields", "No injection"], BLUE),
             ("Receipt injection", ["Private identifier", "+ budget"], AMBER),
             ("Reviewer injection", ["Private budget", "in English words"], AMBER),
             ("Authorized export", ["Full B export", "Explicit permission"], GREEN)]
    for i, (title, lines, fill) in enumerate(cases):
        box(d, i*102, 153, 95, 67, title, lines, fill, title_size=7.3, body_size=7.3)
    # The shared connector denotes inclusion in the fixed design, not execution order.
    for i in range(5):
        d.add(Line(i*102+47.5, 153, i*102+47.5, 143, strokeColor=STROKE, strokeWidth=.8))
    d.add(Line(47.5, 143, 455.5, 143, strokeColor=STROKE, strokeWidth=.8))
    arrow(d, [(251.5, 143), (251.5, 132)])
    box(d, 0, 67, 303, 65, "90 main runs / bounded recovery enabled",
        ["5 cases x 2 actor models x 3 guards x 3 repetitions",
         "Guards: Resource, DLP, Hybrid"], BLUE, body_size=7.8)
    box(d, 320, 67, 183, 65, "6 no-recovery controls",
        ["Receipt injection + DLP only",
         "2 models x 3 repetitions"], AMBER, title_size=8.5, body_size=7.8)
    arrow(d, [(151, 67), (151, 53), (251.5, 53), (251.5, 42)])
    arrow(d, [(411, 67), (411, 53), (251.5, 53)])
    box(d, 116, 0, 271, 42, "96 runs / effects checked independently",
        ["Server events + actual collector receipts"], GREEN, title_size=8.8, body_size=7.8)
    return d


def figures(output_dir=None):
    result = {"architecture": architecture(), "hybrid_recovery": hybrid_recovery(),
              "evaluation_design": evaluation_design()}
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        for name, drawing in result.items():
            path = output_dir / (name + ".svg")
            renderSVG.drawToFile(drawing, str(path))
            # Internal PDF font aliases are not installed browser font families.
            svg = path.read_text().replace(
                "font-family: D-Bold;", "font-family: 'DejaVu Sans', sans-serif; font-weight: bold;")
            svg = svg.replace("font-family: D;", "font-family: 'DejaVu Sans', sans-serif;")
            title = name.replace("_", " ").capitalize()
            svg = svg.replace("<title>...</title>", "<title>" + title + "</title>")
            svg = svg.replace("<desc>...</desc>", "<desc>Vector figure for the MCP proxy manuscript.</desc>")
            path.write_text(svg)
    return result
