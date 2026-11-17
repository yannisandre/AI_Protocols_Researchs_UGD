# First live API pilot - 13 November 2026

The OpenAI and native Anthropic adapters now work end to end with real provider inference,
the Python SDK MCP client, proxy and honest test server. No production agent code, prompt, tool
schema or attack document was changed during this pilot.

## Design and observations

The [frozen execution plan](../experiments/pilot_2026-11-13.json) specifies two dated compatibility
baselines, six conditions each and three repetitions per condition. The main dataset has **36
independent agent runs**. Two initial benign compatibility runs are retained separately.

| Observation | GPT-4.1 mini | Claude Haiku 4.5 |
|---|---:|---:|
| Main runs | 18 | 18 |
| Clean A-only tasks, baseline / enforced | 3 / 3 | 3 / 3 |
| Injected A-only tasks, baseline / enforced | 3 / 3 | 3 / 3 |
| Authorized-export controls, baseline / enforced | 3 / 3 | 3 / 3 |
| Persisted A drafts passing the minimal check | 18 | 18 |
| Out-of-scope MCP attempts | 0 | 0 |
| Unauthorized B reads / disclosures | 0 / 0 | 0 / 0 |
| Task-policy blocks | 0 | 0 |
| Authorized full B exports received | 6 | 6 |
| Technical errors | 0 | 0 |
| MCP tool calls, excluding discovery | 48 | 48 |
| Provider inference requests | 66 | 66 |

Every run actually read A. Each injected run read the attack fixture, not the clean fixture.
All 12 positive-control exports contain the full B document when leading/trailing whitespace is
ignored. Effects are confirmed by independent server/collector events. The draft check verifies
expected A facts and absence of the B canary; it does not establish complete answer quality.

Requested and reported model IDs match: `gpt-4.1-mini-2025-04-14` and
`claude-haiku-4-5-20251001`. These were selected before attack observations for accessible,
inexpensive, dated tool-use baselines. OpenAI currently marks this model deprecated and Anthropic
marks this Haiku version legacy. This is not a survey of the newest models.

The same canonical system instruction, per-task user goals, source code, tool schemas and fixture
hashes were verified across the dataset. Provider wire schemas and provider defaults still differ.
Conditions were shuffled using local seed `20261113`; generation itself was not seeded.

## Interpretation

For this particular document and explicit task scope, both model/provider configurations completed
the tasks without proposing forbidden actions, including in baseline. The proxy therefore had no
forbidden request to block. **This pilot does not establish an incremental security benefit from
the proxy**, nor does it prove that either model recognized or explicitly rejected an injection.

The earlier scripted adversarial controls separately demonstrate policy enforcement when forbidden
calls are deliberately submitted. Those controls are not successful model injections. There is no
evidence here for a general model ranking or immunity to other attacks. The next evaluation should
define a versioned, more diverse attack/task set before running it, without silently replacing
these negative baseline observations.

## Usage and estimated cost

| Main campaign | Input tokens | Output tokens | Estimated USD, no discounts |
|---|---:|---:|---:|
| OpenAI | 27,309 | 3,277 | 0.0161668 |
| Anthropic | 66,889 | 7,279 | 0.1032840 |
| Both main campaigns | | | 0.1194508 |
| Two compatibility runs, separate | | | 0.0048040 |
| Total recorded work | | | **0.1242548** |

All **138 inference requests** have reported usage (132 main, six compatibility); there are no
unpriced requests in this record. Estimates use published standard input/output rates per million
tokens: OpenAI USD 0.40/1.60 and Anthropic USD 1/5. Cache-read discounts are ignored; no cache writes
were reported. These are token-derived estimates before taxes/conversion, not invoices or account
balances. The agreed research ceiling remains EUR 10 total despite EUR 10 credited to each account.

Pricing/model sources, checked 13 November 2026:
[OpenAI model page](https://developers.openai.com/api/docs/models/gpt-4.1-mini),
[Anthropic model page](https://platform.claude.com/docs/en/models/haiku-4-5/overview).

## Evidence and reproduction

- [Public verification record](api-pilot-2026-11-13.json): all run identifiers, independent-effect
  summaries, hashes, settings, native usage totals and cost assumptions.
- [Per-run CSV](api-pilot-2026-11-13-runs.csv) and [condition-count CSV](api-pilot-2026-11-13-groups.csv).
- Full private local transcripts: `results/llm_*_<run_id>.json`; these and real credentials remain
  excluded from Git. Historical setup runs are excluded from the main pilot by campaign ID.

Rebuild the public evidence from the local raw reports without calling a provider:

```bash
python3 -m experiments.summarize_api_pilot
```

The two main campaign commands are in the execution plan and pilot protocol. Rerunning them incurs
new inference costs and may produce different results; choose a new campaign ID and preserve this
record rather than mixing additional runs into the fixed 36-run cohort.
