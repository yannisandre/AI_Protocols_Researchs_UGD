# What to publish, archive and keep local

The Git repository root is one level above `MCP_Proxy/`. Commands below are run from `MCP_Proxy/`
and limit staging to this project. The preparation does not commit or push anything automatically.

## Keep in Git

| Material | Reason |
|---|---|
| Runtime, Docker/Compose files, pinned requirements and preparation script | Reproduce the four-container setup and security boundary |
| All existing tests | Verify authorization, adapters, guards, correction and effect measurement; individual tests need not be named in the paper |
| Synthetic fixtures, plans, manifests and protocols | Explain the cases and reproduce configurations without silently changing historical inputs |
| Sanitized `reference/` records, CSVs and exact source ZIPs | Support current results and the preliminary investigations discussed in Section 6 |
| Manuscript/template, vector figures, two final PDFs and standalone LaTeX ZIP | Read, edit and rebuild the research artifacts |
| Blank `.env*.example` templates | Configure a clone without distributing credentials |
| Documentation and publication check | Explain the current entry points, historical material and local/public separation |

The small duplication between editable LaTeX source, its portable ZIP, and final PDFs is deliberate:
readers can inspect the paper without a compiler or upload the standalone sources separately.

## Keep as clearly labelled history

- `reference/`: historical datasets keep their original paths; its index separates stages.
- `paper/archive/`: the earlier manuscript is not the current paper.
- `output/archive/`: the earlier meeting handout is not mixed with final paper PDFs.
- `compose.codex.yaml`, `lab/codex_agent.py` and corresponding tests: optional host/model integration,
  explained in [the Codex guide](OPTIONAL_CODEX.md), outside the main v2 matrix.

Removing these historical mechanisms would change the implemented scope and provenance. That
would be a new code-maintenance task, not a publication cleanup. No such removal was performed.

## Do not publish

- Actual `.env` files: real actor/judge API keys and local settings.
- `.local/`: per-service credentials, private TLS keys/certificates and raw service logs.
- `results/` except `.gitkeep`: full local conversations, provider responses and run reports.
- `tmp/`, Python/pytest caches and LaTeX compilation intermediates.

These files remain locally available where needed; ignoring them does not delete experiment evidence.
Only regenerable caches/render previews are suitable for routine deletion. The Docker build context
also excludes papers, evidence, temporary files and credentials; the image copies only runtime,
preparation and test sources plus pinned requirements.

## Check and stage

```bash
python3 tools/check_publication.py
git status --short -- .
git add -- .
git diff --cached --stat -- .
git diff --cached --name-only -- .
python3 tools/check_publication.py
```

The check scans tracked and unignored candidate files, including ZIP members, without sending data
to any external service. It detects selected key/private-key patterns and exact local API-key values
when local env files exist; it reports only file names and rule names, never matched secrets.
It also validates local Markdown file targets and frozen runtime/corpus hashes. A clean check is not
a guarantee against every kind of secret or an audit of the rest of the parent repository.

After reviewing the staged diff, make your commit and push from the parent repository using your
normal Git workflow. Avoid `git add -f` for local directories. Do not reuse frozen campaign IDs,
edit historical source ZIPs or replace failed observations while preparing a release.

## Rebuild documents without inference

A clone can update the manuscript from the already-published v2 record:

```bash
python3 -m paper.update_from_recovery
python3 paper/build_pdf.py
python3 paper/build_latex.py --compile
```

The PDF builders require document dependencies, separate from the pinned laboratory image;
ReportLab/DejaVu fonts are used for figures, and LaTeX compilation needs Tectonic or TeX Live.
The [standalone LaTeX instructions](../paper/latex/README.md) describe compilation and Overleaf upload.
The raw-report summarizers and full trace publisher require ignored original reports; do not
overwrite the public records by running them on an empty or unrelated `results/` directory.
