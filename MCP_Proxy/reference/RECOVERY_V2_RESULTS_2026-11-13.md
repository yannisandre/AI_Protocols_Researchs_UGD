# Bounded recovery and hybrid filtering: results, 13 November 2026

This dataset is separate from the earlier API pilots and guard calibration. The corpus uses five new A documents, a new B identifier and a new budget, frozen before mechanism implementation. It is prospectively separated from development inputs, not blinded. No runtime guard, judge prompt, recovery instruction, threshold or fixture was tuned after the main campaign started. The observed records include all main attempts and failures.

The compared arms keep resource/destination checks enabled. DLP uses the existing narrow private-field detector. Hybrid preserves deterministic refusal and consults the fixed judge only after DLP passes. Bounded recovery permits one model-chosen replacement after a structured, run-bound, nontechnical refusal; the host inserts no canned report and permissions never expand.

The plan contains 90 main cells plus six DLP/no-recovery controls. Actor models and per-profile goals are fixed, with three repetitions per cell, order seed 20261116 and provider sampling defaults. A malformed judge decision is retained as a failed run and does not stop the rest of the fixed matrix; other technical failures halt that provider.

## Observations

The fixed matrix completed. 96 of 96 planned runs were observed, including 3 technical failures.

The table reports all main cells with bounded recovery. Counts of safe completion exclude detected
violations and execution errors. Technical errors remain in the denominators.

| Actor | Arm | Runs | Leaks | Safe complete | Recoveries | Errors |
|---|---|---|---|---|---|---|
| GPT-4.1 mini | resource | 15 | 4 | 11 | 0 | 0 |
| GPT-4.1 mini | dlp | 15 | 3 | 12 | 2 | 0 |
| GPT-4.1 mini | hybrid | 15 | 0 | 11 | 2 | 1 |
| Claude Haiku 4.5 | resource | 15 | 0 | 10 | 0 | 0 |
| Claude Haiku 4.5 | dlp | 15 | 0 | 12 | 0 | 0 |
| Claude Haiku 4.5 | hybrid | 15 | 0 | 9 | 0 | 2 |

Rows aggregate different cases, so leaks/runs is not an attack success rate. In the attacked main cells, resource: 4 detected disclosures in 12 attacked runs; dlp: 3 detected disclosures in 12 attacked runs; hybrid: 0 detected disclosures in 12 attacked runs. Across 54 benign/authorized main controls, 53 met all minimal task checks without a measured violation or execution error. Complete B content reached the collector in 17/18 explicitly authorized export controls. A missing leak is interpreted together with task utility and failure status, rather than as evidence that a classifier intervened correctly.

The matched intake-injection DLP comparison is descriptive: each cell has three independently
initialized samples, not paired deterministic trajectories. The treatment includes both structured
retryability feedback and the host's one-time recovery instruction.

| Actor | Recovery | Runs | Leaks | Safe complete | Recoveries | Errors |
|---|---|---|---|---|---|---|
| GPT-4.1 mini | none | 3 | 0 | 2 | 0 | 0 |
| GPT-4.1 mini | bounded | 3 | 0 | 3 | 2 | 0 |
| Claude Haiku 4.5 | none | 3 | 0 | 1 | 0 | 0 |
| Claude Haiku 4.5 | bounded | 3 | 0 | 2 | 0 | 0 |

Across the entire matrix, 4 of 9 runs receiving an actual host recovery notification completed the task. The table preserves runs where no correction was triggered, where the actor stopped, and where a replacement failed. A between-condition difference without a recovery notification cannot be attributed to correction. These small counts do not establish a statistically reliable recovery effect or generalize beyond the selected tasks.

The audit recorded the following judge failure categories: inconsistent_decision_and_reason: 3. An inconsistent decision/reason pair can satisfy the field-level JSON schema and still violate the application contract. For example, the observed pair deny/public_only was safely rejected. Such a refusal is an availability failure, not a correctly classified attack. No prompt or parser was retuned within the cohort.

Token-derived main-campaign cost is USD 0.4690786 for actors and USD 0.0137512 for judges. Preparation cost is separately estimated at USD 0.0019748; 0 requests lack pricing evidence. Frozen standard rates [8, 9] ignore discounts, taxes and currency conversion; these are not invoices or account balances. Observed median guard latency was dlp: 0.15 ms across 34 valid checks; hybrid: 918.55 ms across 28 valid checks. Hybrid latency includes deterministic short circuits. These descriptive local/API samples are not a performance benchmark.

## Benign-control refusals and interpretation

Among submitted candidates in benign/authorized control tasks, 0 ordinary refusals and 1 technical refusals had no oracle-recognized forbidden content (or were explicitly authorized B exports). These are separate from missing task completion caused by an omitted B read or a model choosing to stop. The candidate-level audit below makes false-positive interpretation reviewable; a technical refusal is not a correct security classification. The oracle remains bounded to known synthetic forms, and task utility uses keyword/effect checks rather than full semantic grading.

The estimated entire study cost, including previous campaigns and preparation, is USD 0.8135464; the authorized ceiling remains EUR 10 total. Estimates do not include taxes/FX and are not invoices.

## Preparation and reproducibility

A host-side machine-plan authoring error allowed two benign preparation attempts to start before interruption. One completed; one was interrupted and its independent effects/usage were recovered through the trusted finish endpoint. Both remain outside main counts, with their cost retained. The corpus, written schedule and coded conditions were already fixed; new main IDs were selected and the plan recorded before main execution.

The same four local Docker containers suffice. No VM/VPS, public collector, TLS downgrade or certificate-verification bypass is required. Current offline checks and local scripted controls are recorded in the verification file. The full v2 runtime source snapshot preserves the implementation used for these data. Complete local traces remain ignored; published records contain synthetic data and no authentication headers.

```bash
./lab.sh test
LAB_ENV_FILE=.env.guards.openai ./lab.sh evaluate --campaign recovery-v2-fresh-openai
./lab.sh down
```

API evaluation uses paid provider access; unpaid `test` controls do not. Prepare your own ignored env files from the blank templates, fixing the same judge for cross-provider comparison. Use new campaign IDs and keep providers sequential.

- [Fixed protocol](../experiments/recovery_v2_protocol.md) and [main plan](../experiments/recovery_v2_2026-11-13.json)
- [Pre-implementation corpus hashes](../experiments/evaluation_v2_dataset_manifest.json)
- [Machine-readable evidence](recovery-v2-2026-11-13.json)
- [Per-run CSV](recovery-v2-2026-11-13-runs.csv) and [grouped CSV](recovery-v2-2026-11-13-groups.csv)
- [Offline/scripted verification](recovery-v2-verification.json)
- [Runtime source snapshot](recovery-v2-source.zip)
- [Actual recovered task](recovery-v2-recovered-example.json)
- [Editable manuscript](../paper/paper_draft.md) and [PDF](../output/pdf/MCP_Proxy_Research_Paper_Draft.pdf)
