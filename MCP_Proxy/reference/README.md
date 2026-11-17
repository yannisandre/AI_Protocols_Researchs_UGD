# Evidence index

Start with the fixed v2 evaluation. Earlier records are retained because the paper discusses
preliminary investigations; their runs and versions are not pooled with v2.
All document data in these public records are synthetic. Full raw conversations remain local.

## Main evaluation: hybrid filtering and bounded recovery

- [Readable results](RECOVERY_V2_RESULTS_2026-11-13.md)
- [Audited record](recovery-v2-2026-11-13.json), [per-run CSV](recovery-v2-2026-11-13-runs.csv), [groups](recovery-v2-2026-11-13-groups.csv)
- [Actual completed recovery](recovery-v2-recovered-example.json), [benign-refusal audit](recovery-v2-benign-refusals.json)
- [Preparation starts, excluded from main counts](recovery-v2-preparation-starts.json)
- [Offline/scripted verification](recovery-v2-verification.json), [frozen runtime source](recovery-v2-source.zip)

There are 96 observed main/control runs, including three technical failures. The underlying
`local_report` paths refer to ignored local originals, not missing public download links.

## Preliminary investigations

| Stage | Readable results | Audited data |
|---|---|---|
| Codex host/model | [Results](CODEX_RESULTS.md) | [Verification](codex-verification.json) |
| Initial API pilot | [Results](API_RESULTS_2026-11-13.md) | [JSON](api-pilot-2026-11-13.json), [runs](api-pilot-2026-11-13-runs.csv), [groups](api-pilot-2026-11-13-groups.csv) |
| Authorized reads / public export | [Results](SCENARIO2_RESULTS_2026-11-13.md) | [JSON](scenario2-2026-11-13.json), [runs](scenario2-2026-11-13-runs.csv), [groups](scenario2-2026-11-13-groups.csv), [example](scenario2-openai-example.json) |
| Initial guard calibration | [Results](EXPORT_GUARDS_RESULTS_2026-11-13.md) | [JSON](export-guards-2026-11-13.json), [runs](export-guards-2026-11-13-runs.csv), [groups](export-guards-2026-11-13-groups.csv), [example](export-guards-intent-example.json), [source](export-guards-v1-source.zip) |

Older integration verification files are [scripted](scripted-verification.json),
[API prototype](prototype-verification-2026-11-13.json),
[scenario 2](scenario2-scripted-verification.json) and
[guard calibration](export-guards-verification-2026-11-13.json).
See [research history](../docs/HISTORY.md) for interpretation and source-version boundaries.
Keep historical records and ZIPs unchanged; use new campaigns for new experiments.
