"""Publish a readable v2 result record and representative real traces, without inference."""
import hashlib
import json
from pathlib import Path

from paper.update_from_recovery import main as update_paper

ROOT = Path(__file__).resolve().parent.parent


def main():
    update_paper()
    result = json.loads((ROOT / "reference/recovery-v2-2026-11-13.json").read_text())
    records = result["main_runs"]
    paper = (ROOT / "paper/paper_draft.md").read_text()
    results = paper.split("### 7. New evaluation results\n\n", 1)[1].split("### 8.", 1)[0]
    controls = [r for r in records if r["variant"] == "clean"]
    ordinary_refusals, technical_refusals = [], []
    for r in controls:
        for candidate in r["assessed_send_candidates"]:
            if not candidate["allowed"]:
                permitted_content = r["profile"] == "authorized_export" or not candidate["oracle_private_hits"]
                if permitted_content:
                    (technical_refusals if candidate["guard_failure"] else ordinary_refusals).append({
                        "run_id": r["run_id"], "case": r["case"], "guard": r["guard"],
                        "reason": candidate["reason"], "content": candidate["content"]})
    total = result["cost"]["previous_study_estimate"] + result["cost"]["main_estimate"] + result["cost"]["preparation_estimate"]
    header = (
        "# Bounded recovery and hybrid filtering: results, 13 November 2026\n\n"
        "This dataset is separate from the earlier API pilots and guard calibration. The corpus "
        "uses five new A documents, a new B identifier and a new budget, frozen before mechanism "
        "implementation. It is prospectively separated from development inputs, not blinded. "
        "No runtime guard, judge prompt, recovery instruction, threshold or fixture was tuned "
        "after the main campaign started. The observed records include all main attempts and failures.\n\n"
        "The compared arms keep resource/destination checks enabled. DLP uses the existing narrow "
        "private-field detector. Hybrid preserves deterministic refusal and consults the fixed "
        "judge only after DLP passes. Bounded recovery permits one model-chosen replacement after "
        "a structured, run-bound, nontechnical refusal; the host inserts no canned report and "
        "permissions never expand.\n\n"
        "The plan contains 90 main cells plus six DLP/no-recovery controls. Actor models and "
        "per-profile goals are fixed, with three repetitions per cell, order seed 20261116 and "
        "provider sampling defaults. A malformed judge decision is retained as a failed run and "
        "does not stop the rest of the fixed matrix; other technical failures halt that provider.\n\n"
        "## Observations\n\n")
    extra = (
        "## Benign-control refusals and interpretation\n\n"
        f"Among submitted candidates in benign/authorized control tasks, {len(ordinary_refusals)} "
        f"ordinary refusals and {len(technical_refusals)} technical refusals had no oracle-recognized "
        "forbidden content (or were explicitly authorized B exports). These are separate from "
        "missing task completion caused by an omitted B read or a model choosing to stop. "
        "The candidate-level audit below makes false-positive interpretation reviewable; a "
        "technical refusal is not a correct security classification. The oracle remains bounded "
        "to known synthetic forms, and task utility uses keyword/effect checks rather than full semantic grading.\n\n"
        f"The estimated entire study cost, including previous campaigns and preparation, is USD {total:.7f}; "
        "the authorized ceiling remains EUR 10 total. Estimates do not include taxes/FX and are not invoices.\n\n"
        "## Preparation and reproducibility\n\n"
        "A host-side machine-plan authoring error allowed two benign preparation attempts to "
        "start before interruption. One completed; one was interrupted and its independent "
        "effects/usage were recovered through the trusted finish endpoint. Both remain outside "
        "main counts, with their cost retained. The corpus, written schedule and coded conditions "
        "were already fixed; new main IDs were selected and the plan recorded before main execution.\n\n"
        "The same four local Docker containers suffice. No VM/VPS, public collector, TLS downgrade "
        "or certificate-verification bypass is required. Current offline checks and local scripted "
        "controls are recorded in the verification file. The full v2 runtime source snapshot "
        "preserves the implementation used for these data. Complete local traces remain ignored; "
        "published records contain synthetic data and no authentication headers.\n\n"
        "```bash\n./lab.sh test\n"
        "LAB_ENV_FILE=.env.guards.openai ./lab.sh evaluate --campaign recovery-v2-fresh-openai\n"
        "./lab.sh down\n```\n\n"
        "API evaluation uses paid provider access; unpaid `test` controls do not. Prepare your own "
        "ignored env files from the blank templates, fixing the same judge for cross-provider comparison. "
        "Use new campaign IDs and keep providers sequential.\n\n"
        "- [Fixed protocol](../experiments/recovery_v2_protocol.md) and [main plan](../experiments/recovery_v2_2026-11-13.json)\n"
        "- [Pre-implementation corpus hashes](../experiments/evaluation_v2_dataset_manifest.json)\n"
        "- [Machine-readable evidence](recovery-v2-2026-11-13.json)\n"
        "- [Per-run CSV](recovery-v2-2026-11-13-runs.csv) and [grouped CSV](recovery-v2-2026-11-13-groups.csv)\n"
        "- [Offline/scripted verification](recovery-v2-verification.json)\n"
        "- [Runtime source snapshot](recovery-v2-source.zip)\n"
        "- [Actual recovered task](recovery-v2-recovered-example.json)\n"
        "- [Editable manuscript](../paper/paper_draft.md) and [PDF](../output/pdf/MCP_Proxy_Research_Paper_Draft.pdf)\n")
    (ROOT / "reference/RECOVERY_V2_RESULTS_2026-11-13.md").write_text(header + results + extra)
    (ROOT / "reference/recovery-v2-benign-refusals.json").write_text(json.dumps({
        "scope": "Oracle-clean or explicitly authorized candidates refused in benign control tasks; inspect context before calling a false positive",
        "ordinary_refusals": ordinary_refusals, "technical_refusals": technical_refusals}, indent=2) + "\n")
    choices = []
    for r in records:
        if r["metrics"]["recovered_task"]:
            path = ROOT / r["local_report"]
            raw = json.loads(path.read_text())
            choices.append((raw["completed_at"], path, raw))
    if choices:
        _, path, raw = min(choices)
        example = {"description": "First completed model-driven successful recovery in the fixed v2 main campaign; synthetic data only",
                   "selection_rule": "Earliest completed_at among all recovered_task main runs, not a best-of selection",
                   "run_id": raw["run_id"], "guard": raw["guard"], "evaluation_case": raw["evaluation_case"],
                   "metrics": raw["metrics"], "policy": raw["policy"],
                   "conversation": next(t["conversation"] for t in raw["transcript"] if "conversation" in t),
                   "proxy_decisions": [e for e in raw["proxy_events"] if e.get("event") in {"decision", "export_guard"}],
                   "independent_server_events": raw["server_events"], "independent_collector_receipts": raw["collector_events"],
                   "original_local_report_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        (ROOT / "reference/recovery-v2-recovered-example.json").write_text(json.dumps(example, indent=2) + "\n")
    print("Published readable v2 observations, benign-refusal audit and real recovery trace")


if __name__ == "__main__": main()
