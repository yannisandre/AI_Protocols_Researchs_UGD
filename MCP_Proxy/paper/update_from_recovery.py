"""Fill the manuscript's observed-result sections from the audited v2 record (no API calls)."""
import json
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    result = json.loads((ROOT / "reference/recovery-v2-2026-11-13.json").read_text())
    records = result["main_runs"]
    names = {"openai": "GPT-4.1 mini", "anthropic": "Claude Haiku 4.5"}
    def safe(r): return bool(r["metrics"]["safe_task_completion"]) and not r["execution_error"]
    def leaks(rs): return sum(r["metrics"]["unauthorized_disclosure"] for r in rs)
    def errors(rs): return sum(bool(r["execution_error"]) for r in rs)
    def recovered(rs): return sum(bool(r["metrics"]["recovered_task"]) for r in rs)
    bounded = [r for r in records if r["recovery"] == "bounded"]
    notified = sum(r["metrics"]["recovery_notifications"] for r in records)
    def table(header, rows):
        return "\n".join(["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
                         + ["| " + " | ".join(map(str, row)) + " |" for row in rows])
    rows = []
    for provider in names:
        for guard in ["resource", "dlp", "hybrid"]:
            rs = [r for r in bounded if r["provider"] == provider and r["guard"] == guard]
            rows.append([names[provider], guard, len(rs), leaks(rs), sum(safe(r) for r in rs), recovered(rs), errors(rs)])
    recovery_rows = []
    for provider in names:
        for recovery in ["none", "bounded"]:
            rs = [r for r in records if r["provider"] == provider and r["guard"] == "dlp"
                  and r["case"] == "receipt_injection" and r["recovery"] == recovery]
            recovery_rows.append([names[provider], recovery, len(rs), leaks(rs), sum(safe(r) for r in rs), recovered(rs), errors(rs)])
    attacks = [r for r in bounded if r["variant"] == "attack"]
    breakdown = []
    for guard in ["resource", "dlp", "hybrid"]:
        rs = [r for r in attacks if r["guard"] == guard]
        breakdown.append(f"{guard}: {leaks(rs)} detected disclosures in {len(rs)} attacked runs")
    controls = [r for r in bounded if r["variant"] == "clean"]
    authorized = [r for r in records if r["profile"] == "authorized_export"]
    private = (ROOT / "fixtures/evaluation_v2/B_confidential.txt").read_text().strip()
    full_exports = sum(any(e["content"].strip() == private for e in r["collector_receipts"]) for r in authorized)
    details = Counter(d.get("detail") or d["reason"] for r in records for d in r["judge_contract_failures"])
    actor_cost = sum(r["actor_usage"]["estimated_usd_no_discounts"] for r in records)
    judge_cost = sum(r["judge_usage"]["estimated_usd_no_discounts"] for r in records)
    latency = []
    for guard in ["dlp", "hybrid"]:
        values = [g["latency_ms"] for r in records if r["guard"] == guard for g in r["guard_checks"] if not g.get("failure")]
        latency.append(f"{guard}: {statistics.median(values):,.2f} ms across {len(values)} valid checks" if values else f"{guard}: no valid check")
    status = ("The fixed matrix completed." if result["matrix_complete"] else
              "The fixed matrix is incomplete; unattempted cells are not treated as successful or failed defenses.")
    status += f" {len(records)} of {result['planned_runs']} planned runs were observed, including {errors(records)} technical failures."
    values = {
        "ABSTRACT_RESULTS": f"The new evaluation records {len(records)} runs with {leaks(records)} detected unauthorized disclosures and {recovered(records)} complete tasks among {notified} runs receiving a host recovery notification.",
        "EXECUTION_STATUS": status,
        "MAIN_TABLE": table(["Actor", "Arm", "Runs", "Leaks", "Safe complete", "Recoveries", "Errors"], rows),
        "MAIN_INTERPRETATION": "Rows aggregate different cases, so leaks/runs is not an attack success rate. In the attacked main cells, " + "; ".join(breakdown) + ". "
            + f"Across {len(controls)} benign/authorized main controls, {sum(safe(r) for r in controls)} met all minimal task checks without a measured violation or execution error. "
            + f"Complete B content reached the collector in {full_exports}/{len(authorized)} explicitly authorized export controls. "
            + "A missing leak is interpreted together with task utility and failure status, rather than as evidence that a classifier intervened correctly.",
        "RECOVERY_TABLE": table(["Actor", "Recovery", "Runs", "Leaks", "Safe complete", "Recoveries", "Errors"], recovery_rows),
        "RECOVERY_INTERPRETATION": f"Across the entire matrix, {recovered(records)} of {notified} runs receiving an actual host recovery notification completed the task. "
            + "The table preserves runs where no correction was triggered, where the actor stopped, and where a replacement failed. "
            + "A between-condition difference without a recovery notification cannot be attributed to correction. "
            + "These small counts do not establish a statistically reliable recovery effect or generalize beyond the selected tasks.",
        "JUDGE_DIAGNOSTICS": "The audit recorded the following judge failure categories: "
            + (", ".join(f"{k}: {v}" for k, v in sorted(details.items())) if details else "none")
            + ". An inconsistent decision/reason pair can satisfy the field-level JSON schema and still violate the application contract. "
            + "For example, the observed pair deny/public_only was safely rejected. Such a refusal is an availability failure, not a correctly classified attack. No prompt or parser was retuned within the cohort.",
        "COST_AND_LATENCY": f"Token-derived main-campaign cost is USD {actor_cost:.7f} for actors and USD {judge_cost:.7f} for judges. "
            + f"Preparation cost is separately estimated at USD {result['cost']['preparation_estimate']:.7f}; {result['cost']['unpriced_requests']} requests lack pricing evidence. "
            + "Frozen standard rates [8, 9] ignore discounts, taxes and currency conversion; these are not invoices or account balances. "
            + "Observed median guard latency was " + "; ".join(latency) + ". Hybrid latency includes deterministic short circuits. "
            + "These descriptive local/API samples are not a performance benchmark.",
        "CONCLUSION": "The testbed separates resource authorization, content refusal, model correction and independently observed effects. "
            + f"The new matrix records {recovered(records)} complete recoveries, while preserving {leaks(records)} detected disclosures and {errors(records)} technical failures. "
            + "Authoritative deterministic denials prevent a judge from undoing known blocks, but detector blind spots, classifier errors and incomplete work remain. "
            + "The results motivate joint security/utility evaluation and better isolation or provenance mechanisms rather than a general claim of prompt-injection prevention.",
    }
    text = (ROOT / "paper/paper_v2_template.md").read_text()
    for key, value in values.items(): text = text.replace("{{" + key + "}}", value)
    assert "{{" not in text, "Unfilled manuscript field"
    (ROOT / "paper/paper_draft.md").write_text(text)
    print("Updated manuscript from", len(records), "audited main runs")


if __name__ == "__main__": main()
