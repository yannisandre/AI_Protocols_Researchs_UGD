# Two-column manuscript source

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
