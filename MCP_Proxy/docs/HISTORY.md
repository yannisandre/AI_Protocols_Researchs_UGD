# Research history and dataset separation

This index distinguishes development observations from the fixed evaluation used in the paper.
It is not a pooled benchmark. The cleanup on 17 November 2026 changes documentation/publication
organization, not experimental inputs, runtime mechanisms, published numbers or frozen records.

| Stage | Question / role | Evidence |
|---|---|---|
| Initial scripted controls | Does the real SDK path enforce a prescribed task boundary and record effects? No model attack efficacy is measured. | [Verification](../reference/scripted-verification.json) |
| Codex, 30 October | Does the complete Codex host/model follow the A-document injection? Six turns stayed in scope, including without filtering; no incremental proxy protection was demonstrated. | [Results](../reference/CODEX_RESULTS.md), [record](../reference/codex-verification.json) |
| Initial API pilot, 13 November | Two dated model configurations, 36 main runs plus two compatibility runs. No forbidden attempts; useful integration evidence, not an observed defense benefit. | [Results](../reference/API_RESULTS_2026-11-13.md), [record](../reference/api-pilot-2026-11-13.json) |
| Authorized reads / public export | In 36 API runs, reading B and using an allowed destination did not prevent private-content export. Six injected OpenAI runs disclosed B; Claude had no detected leak but incomplete work in some cases. | [Results](../reference/SCENARIO2_RESULTS_2026-11-13.md), [record](../reference/scenario2-2026-11-13.json) |
| Pre-send guard calibration | Partial development-visible evaluation: 11 actor runs and 25 constructed gateway cases. DLP blind spots, an incorrect judge approval and contract failures were retained. | [Results](../reference/EXPORT_GUARDS_RESULTS_2026-11-13.md), [record](../reference/export-guards-2026-11-13.json) |
| Fixed v2 evaluation | New synthetic wording/values fixed before implementation; 96 planned runs all attempted. Resource, DLP and hybrid with bounded correction, plus a narrow no-recovery comparison. | [Main results](../reference/RECOVERY_V2_RESULTS_2026-11-13.md), [record](../reference/recovery-v2-2026-11-13.json) |

## What belongs to the current paper

Sections 3-5 describe the current threat model, mechanism and method. Section 6 explicitly discusses
the development stages above; Section 7 reports v2. Earlier evidence is therefore retained for the
paper's claims, rather than discarded because it predates the final experiment.

The five v2 cases are a plain public summary, benign public metadata, an intake-receipt injection,
a reviewer-stamp injection asking for the budget in words, and explicitly authorized full B export.
Ninety main runs enable bounded recovery. Six additional runs disable it only for receipt injection
under DLP: three per actor model. Recovery enabled is not the same as a host correction triggered.

There were seven detected disclosures, three technical judge failures and four completed tasks
among nine runs receiving a host correction. Hybrid had no detected disclosure in 30 main runs,
but only 20 safe task completions. Small synthetic samples and bounded detection do not establish
general confidentiality, model rankings or a statistically reliable recovery benefit.

Two benign preparation attempts remain outside main counts, with their effects/cost recorded in
[preparation evidence](../reference/recovery-v2-preparation-starts.json). Invalid judge runs were
retained without replacement. Do not repair the historical data by dropping failed runs.

## Frozen material and later changes

- [V2 corpus manifest](../experiments/evaluation_v2_dataset_manifest.json): synthetic documents fixed before implementation.
- [V2 plan](../experiments/recovery_v2_2026-11-13.json): campaign names, versions, settings, hashes and rates.
- [V2 source ZIP](../reference/recovery-v2-source.zip): exact runtime snapshot for those results.
- [Verification](../reference/recovery-v2-verification.json): 104 offline checks and 15 scripted controls.

Existing file paths in `reference/`, `fixtures/` and `experiments/` are deliberately stable.
Source snapshots are historical records, not copies to update during cleanup. The current root
launcher adds an `evaluate` shortcut relative to the original v2 snapshot; the snapshot's explicit
Compose invocation remains documented. The runtime/corpus hashes remain unchanged.

Manuscript wording and figures were refined after evaluation. Both final PDF layouts share the same
results, and the disclosure records AI assistance in writing, architecture, code, tests and analysis.
The [old API-pilot manuscript](../paper/archive/paper_api_pilot_2026-11-13.md) and
[meeting handout](../output/archive/MCP_Proxy_Meeting_Brief.pdf) are historical documents.

Full local conversations stay in ignored `results/` and `.local/`. Public records provide selected
synthetic traces, counts, costs and hashes; they are not a complete release of every raw transcript.
Recomputing raw-trace summaries needs those original local reports. New paid experiments require
new campaign IDs and remain distinct from the frozen datasets.
