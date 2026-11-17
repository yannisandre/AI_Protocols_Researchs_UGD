"""Generate a self-contained two-column LaTeX edition of the existing manuscript.

Requires the same ReportLab/fonts as build_pdf.py. Compilation is optional and
uses Tectonic, latexmk, or pdflatex; no research inference calls are performed.
"""
import argparse
import hashlib
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from reportlab.graphics import renderPDF
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from diagrams import figures

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
LATEX = ROOT / "latex"
PDF = REPO / "output/pdf/MCP_Proxy_Research_Paper_Two_Column.pdf"
ARCHIVE = REPO / "output/MCP_Proxy_LaTeX_Source.zip"


def escape(text):
    replacements = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
                    "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
                    "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(replacements.get(c, c) for c in text)


def inline(text):
    # Tokenize before escaping so citations, URLs and inline styles stay intact.
    pattern = r"(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|https://[^\s]+|\[\d+(?:,\s*\d+)*\])"
    parts = re.split(pattern, text)
    result = []
    for part in parts:
        if part.startswith("`"):
            result.append(r"\texttt{" + escape(part[1:-1]) + "}")
        elif part.startswith("**"):
            result.append(r"\textbf{" + escape(part[2:-2]) + "}")
        elif part.startswith("*"):
            result.append(r"\emph{" + escape(part[1:-1]) + "}")
        elif part.startswith("https://"):
            result.append(r"\url{" + part + "}")
        elif re.fullmatch(r"\[\d+(?:,\s*\d+)*\]", part):
            keys = ["ref" + n.strip() for n in part[1:-1].split(",")]
            result.append(r"\cite{" + ",".join(keys) + "}")
        else:
            result.append(escape(part))
    return "".join(result)


def blocks(text):
    return [" ".join(line.strip() for line in block.splitlines())
            if not block.lstrip().startswith("|") else block
            for block in re.split(r"\n\s*\n", text.strip())]


def table(block, index):
    rows = [[c.strip() for c in line.strip().strip("|").split("|")]
            for line in block.splitlines() if line.strip()]
    rows = [row for row in rows if not all(re.fullmatch(r":?-+:?", c) for c in row)]
    caption = ("Main evaluation: bounded recovery enabled. Errors remain in the denominators; "
               "rows include benign, attacked and authorized-export cases." if index == 1 else
               "Receipt-injection DLP comparison with and without bounded recovery. "
               "Each row contains three independent runs.")
    label = "main-results" if index == 1 else "recovery-results"
    header = [r"\textbf{" + inline(x) + "}" for x in rows[0]]
    data = [" & ".join(inline(c) for c in row) + r" \\" for row in rows[1:]]
    return "\n".join([
        r"\begin{table*}[t]", r"\centering", r"\caption{" + caption + "}",
        r"\label{tab:" + label + "}", r"\small", r"\setlength{\tabcolsep}{8pt}",
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}llrrrrr@{}}", r"\toprule",
        " & ".join(header) + r" \\", r"\midrule", *data,
        r"\bottomrule", r"\end{tabular*}", r"\end{table*}"])


PREAMBLE = r"""% Generated from ../paper_draft.md; see README.md for regeneration.
\documentclass[10pt,twocolumn,letterpaper]{article}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{newtxtext}
\usepackage[letterpaper,left=0.75in,right=0.75in,top=0.75in,bottom=0.8in,columnsep=0.25in]{geometry}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{microtype}
\usepackage{caption}
\usepackage{titlesec}
\usepackage{xurl}
\usepackage[hidelinks]{hyperref}
\usepackage{flushend}
\graphicspath{{figures/}}
\hypersetup{pdftitle={Task Authorization, Export Guards and Bounded Recovery at the MCP Boundary},pdfauthor={Yannis ANDRE}}
\setlength{\parindent}{1em}
\setlength{\parskip}{0pt}
\setlength{\textfloatsep}{12pt plus 2pt minus 2pt}
\setlength{\dbltextfloatsep}{13pt plus 2pt minus 2pt}
\setlength{\floatsep}{10pt plus 2pt minus 2pt}
\renewcommand{\topfraction}{0.95}
\renewcommand{\dbltopfraction}{0.95}
\renewcommand{\textfraction}{0.05}
\renewcommand{\floatpagefraction}{0.8}
\renewcommand{\dblfloatpagefraction}{0.8}
\setcounter{topnumber}{3}
\setcounter{dbltopnumber}{1}
\setcounter{totalnumber}{5}
\captionsetup{font=small,labelfont=bf,skip=5pt}
\titleformat{\section}{\large\bfseries}{\thesection}{0.65em}{}
\titlespacing*{\section}{0pt}{9pt plus 2pt minus 1pt}{4pt}
\urlstyle{same}
\emergencystretch=1.2em
\clubpenalty=10000
\widowpenalty=10000
\pagestyle{plain}
\raggedbottom
\begin{document}
"""


def generate():
    manuscript = (ROOT / "paper_draft.md").read_text()
    header, body = manuscript.split("### Abstract", 1)
    front = blocks(header)
    assert len(front) == 5, "Unexpected manuscript front matter"
    title = front[0].lstrip("# ")
    source_hash = hashlib.sha256(manuscript.encode()).hexdigest()
    pieces = [PREAMBLE, "% Manuscript SHA-256: " + source_hash,
              r"\twocolumn[{", r"\begin{center}", r"{\LARGE\bfseries " + inline(title) + r"\par}",
              r"\vspace{9pt}", inline(front[1]) + r"\par", r"\vspace{4pt}",
              r"{\small " + inline(front[2]) + r"\par}", r"\vspace{5pt}",
              r"{\small " + inline(front[3]) + r"\par}", r"\end{center}",
              r"\noindent\begin{minipage}{\textwidth}\footnotesize " + inline(front[4]) +
              r"\end{minipage}", r"\vspace{12pt}", r"}]", r"\section*{Abstract}"]
    body_blocks = blocks(body)
    image_blocks = [b for b in body_blocks if b.startswith("![")]
    table_blocks = [b for b in body_blocks if b.startswith("|")]
    assert len(image_blocks) == 3 and len(table_blocks) == 2
    def figure(block):
        match = re.fullmatch(r"!\[(.+)\]\(figures/([a-z_]+)\.svg\)", block)
        assert match, block
        caption = re.sub(r"^Figure \d+\.\s*", "", match[1])
        return "\n".join([r"\begin{figure*}[t]", r"\centering",
                          r"\includegraphics[width=\textwidth]{" + match[2] + ".pdf}",
                          r"\caption{" + inline(caption) + "}",
                          r"\label{fig:" + match[2] + "}", r"\end{figure*}"])
    # Declare wide floats at the start of their section so they can appear at
    # the top of the next page rather than accumulating behind later sections.
    floats = {3: figure(image_blocks[0]), 4: figure(image_blocks[1]), 5: figure(image_blocks[2])}
    main_table, recovery_table = [table(b, i+1) for i, b in enumerate(table_blocks)]
    # Queue the result tables before the preliminary-study section so their
    # next-page float lands beside the main results, ahead of the bibliography.
    floats[6] = (main_table.removesuffix(r"\end{table*}") + r"\par\vspace{10pt}" + "\n" +
                 recovery_table.removeprefix("\\begin{table*}[t]\n\\centering\n"))
    refs = False
    for block in body_blocks:
        if block == "### References":
            refs = True
            pieces.extend([r"\begin{thebibliography}{99}", r"\small\raggedright\interlinepenalty=10000"])
        elif refs:
            match = re.match(r"\[(\d+)\]\s*(.*)", block)
            assert match, block
            pieces.append(r"\bibitem{ref" + match[1] + "} " + inline(match[2]))
        elif block.startswith("### "):
            section_number = int(re.match(r"### (\d+)\.", block)[1])
            if section_number in floats:
                pieces.append(floats[section_number])
            name = re.sub(r"^### \d+\.\s*", "", block)
            pieces.append(r"\section{" + inline(name) + "}")
        elif block.startswith(("![", "|")):
            continue
        else:
            text = inline(block)
            if block.startswith("Four Docker containers run"):
                text += r" Figure~\ref{fig:architecture} summarizes these components and connections."
            elif block.startswith("The **hybrid arm**"):
                text += r" Figure~\ref{fig:hybrid_recovery} shows the pre-send control and correction paths."
            elif block.startswith("The plan has three repetitions"):
                text += r" Figure~\ref{fig:evaluation_design} summarizes the fixed matrix."
            elif block.startswith("The table reports all main cells"):
                text = text.replace("The table reports", r"Table~\ref{tab:main-results} reports", 1)
            elif block.startswith("The matched intake-injection DLP comparison"):
                text = text.replace("comparison is descriptive", r"comparison in Table~\ref{tab:recovery-results} is descriptive", 1)
            pieces.append(text + "\n")
    pieces.extend([r"\end{thebibliography}", r"\end{document}", ""])
    LATEX.mkdir(parents=True, exist_ok=True)
    (LATEX / "main.tex").write_text("\n".join(pieces))
    for name, filename in [("D", "DejaVuSans.ttf"), ("D-Bold", "DejaVuSans-Bold.ttf")]:
        pdfmetrics.registerFont(TTFont(name, "/usr/share/fonts/truetype/dejavu/" + filename))
    assets = LATEX / "figures"
    assets.mkdir(exist_ok=True)
    for name, drawing in figures().items():
        renderPDF.drawToFile(drawing, str(assets / (name + ".pdf")))
    (LATEX / "README.md").write_text("""# Two-column manuscript source

This is a standalone LaTeX edition of the existing MCP proxy manuscript, not an
official conference template and not a claim of publication or acceptance.
The source preserves the manuscript's text, measured results, supervision and
AI-assistance disclosure. Figure and table positions may change through floating.

## Compile

Upload `main.tex` and the `figures/` directory together to Overleaf, or run:

```
tectonic main.tex
```

Alternatively, run `pdflatex main.tex` twice with a TeX Live distribution providing
newtxtext, microtype, caption, titlesec, xurl, booktabs, flushend and hyperref.

## Regenerate from the repository manuscript

From the repository root, with the document dependencies installed:

```
python3 paper/build_latex.py --compile
```

An explicit compiler path can be supplied with `--engine /path/to/tectonic`.
Without `--compile`, the script generates the source, vector PDFs and ZIP only.
Edit `paper/paper_v2_template.md`, regenerate `paper/paper_draft.md` with
`python3 -m paper.update_from_recovery`, then regenerate this edition to retain
changes across future builds. Direct changes to main.tex will be overwritten.
The original single-column PDF is never modified by this build.
""")
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARCHIVE, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(LATEX.rglob("*")):
            if file.is_file() and (file.suffix in {".tex", ".pdf"} or file.name == "README.md"):
                archive.write(file, file.relative_to(LATEX))
    print("LaTeX source:", LATEX / "main.tex", flush=True)
    print("Portable source ZIP:", ARCHIVE, flush=True)


def compile_pdf(engine):
    executable = engine or shutil.which("tectonic") or shutil.which("latexmk") or shutil.which("pdflatex")
    if not executable:
        raise SystemExit("Source generated. Compile with Tectonic/TeX Live or supply --engine PATH.")
    build = REPO / "tmp/pdfs/latex-build"
    build.mkdir(parents=True, exist_ok=True)
    name = Path(executable).name
    if "tectonic" in name:
        command = [executable, "--keep-logs", "--outdir", str(build), "main.tex"]
        subprocess.run(command, cwd=LATEX, check=True)
    elif "latexmk" in name:
        command = [executable, "-pdf", "-interaction=nonstopmode", "-halt-on-error", "-outdir="+str(build), "main.tex"]
        subprocess.run(command, cwd=LATEX, check=True)
    else:
        command = [executable, "-interaction=nonstopmode", "-halt-on-error", "-output-directory="+str(build), "main.tex"]
        for _ in range(2):
            subprocess.run(command, cwd=LATEX, check=True)
    PDF.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(build / "main.pdf", PDF)
    print("Two-column PDF:", PDF, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--compile", action="store_true", help="Compile the generated source with a local TeX engine")
    parser.add_argument("--engine", help="Explicit path to Tectonic, latexmk, or pdflatex")
    args = parser.parse_args()
    generate()
    if args.compile:
        compile_pdf(args.engine)
