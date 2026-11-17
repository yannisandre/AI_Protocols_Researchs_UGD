# Test purposes

These are offline checks, not observed prompt-injection success rates. Retain them even when
the paper describes the property rather than citing a test name. The verified suite has 104 cases,
including parameterized cases; `./lab.sh test` additionally runs 15 scripted controls.

| Files | Property checked |
|---|---|
| `test_policy.py`, `test_boundary.py` | Separate task permissions from account rights; validate arguments; protect host control, run binding and upstream headers; refuse before an upstream effect |
| `test_providers.py`, `test_agent_loop.py` | Preserve actual provider tool-call/result contracts; record technical failures and close/report runs |
| `test_guards.py` | Known-field DLP behavior and explicit blind spots; separation of trusted policy and untrusted content; strict judge contracts |
| `test_recovery.py`, `test_recovery_loop.py` | Recognize typed eligible refusals; add at most one host correction; keep permissions and private content out of that correction |
| `test_evaluation.py`, `test_analysis.py` | Measure independent effects; do not count leaks/errors as safe tasks or pool incompatible cohorts; retain known oracle limitations |
| `test_codex_driver.py` | Optional historical Codex driver: credential handling, real turn dispatch and rejection of unexpected tool activity |

The optional Codex tests use fake credentials/replies and no model call. The 15 scripted controls
also use prescribed behavior: they establish integration/enforcement, not model resistance.
The real-model experiments are separately defined in [the experiment index](../experiments/README.md).
