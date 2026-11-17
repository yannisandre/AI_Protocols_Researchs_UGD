# Experiment index

These are versioned experimental designs and post-processing scripts, not the unit test suite.
The main paper distinguishes preliminary investigations from its fixed v2 evaluation.

| Dataset | Protocol | Execution plan |
|---|---|---|
| Main v2: hybrid + bounded recovery | [Protocol](recovery_v2_protocol.md) | [Plan](recovery_v2_2026-11-13.json), [corpus manifest](evaluation_v2_dataset_manifest.json) |
| Initial API pilot | [Protocol](pilot_protocol.md) | [Plan](pilot_2026-11-13.json) |
| Authorized reads / public export | [Protocol](scenario2_protocol.md) | [Plan](scenario2_2026-11-13.json) |
| Pre-send calibration | [Protocol](export_guards_protocol.md) | [Plan](export_guards_2026-11-13.json) |

`lab.evaluate_v2` runs the 48-task/provider fixed design through real model APIs. New observations
require new campaign IDs; provider access, cost and outputs are not guaranteed by the frozen record.

The `summarize_*.py` scripts recompute public evidence from original local reports. They need the
corresponding ignored `results/` files. `summarize_recovery_v2.py` imports the shared cost helper
from `summarize_export_guards.py`, so the earlier script is still a dependency of the main analysis.
`publish_recovery_v2.py` also uses local reports to select the first completed recovery trace.

A clean clone can inspect [published evidence](../reference/README.md) and regenerate the editable
paper with `python3 -m paper.update_from_recovery` without raw reports or model calls.
Frozen plans, inputs and historical records are not modified during publication cleanup.
