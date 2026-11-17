"""Rebuild sanitized scenario-2 evidence from independent effects and full local traces."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from lab.analyze import flatten, group_rows
from lab.evaluation import content_hits, evaluate_effects
from lab.provenance import json_hash

ROOT = Path(__file__).resolve().parent.parent


def summarize():
    plan_path = ROOT / "experiments/scenario2_2026-11-13.json"
    plan = json.loads(plan_path.read_text())
    specs = {m["campaign"]: m for m in plan["models"]}
    rows, records = [], []
    private_text = (ROOT / "fixtures/B_confidential.txt").read_text().strip()
    canary = next(l.split("Canary: ", 1)[1] for l in private_text.splitlines() if l.startswith("Canary: "))
    fields = {"B_budget": "42,000 imaginary credits"}
    for path in sorted((ROOT / "results").glob("llm_*.json")):
        r = json.loads(path.read_text())
        spec = specs.get((r.get("experiment") or {}).get("campaign"))
        if spec is None:
            continue
        config = r["llm_configuration"]
        assert r["scenario"] == plan["scenario"] and r["oracle_version"] == plan["oracle_version"]
        assert config["provider"] == spec["provider"] and config["model_requested"] == spec["model"]
        assert config["max_requests"] == plan["max_requests_per_run"]
        assert config["max_completion_tokens"] == plan["max_generated_tokens_per_request"]
        assert r["source_sha256"] == plan["source_sha256"], "Code changed from frozen plan"
        assert r["fixture_hashes"] == plan["fixture_sha256"], "Fixtures changed from frozen plan"
        assert r["protocol_version"] == "2026-07-28"
        expected = evaluate_effects(r["policy"], r["profile"], r["server_events"],
                                    r["collector_events"], canary, fields)
        assert all(r["metrics"][k] == v for k, v in expected.items()), "Metric/effect mismatch"
        usage = [e for e in r["proxy_events"] if e.get("event") == "llm_usage"]
        inputs = outputs = cache_read = cache_write = missing = 0
        for e in usage:
            u = e.get("usage", {})
            a, b = (("prompt_tokens", "completion_tokens") if spec["provider"] == "openai"
                    else ("input_tokens", "output_tokens"))
            missing += a not in u or b not in u
            inputs += u.get(a, 0)
            outputs += u.get(b, 0)
            if spec["provider"] == "anthropic":
                cache_read += u.get("cache_read_input_tokens", 0)
                cache_write += u.get("cache_creation_input_tokens", 0)
        rates = spec["pricing_usd_per_million_tokens"]
        cost = ((inputs + cache_read + 2 * cache_write) * rates["input"] + outputs * rates["output"]) / 1e6
        messages = next(t["conversation"] for t in r["transcript"] if "conversation" in t)
        receipts = r["collector_events"]
        # Publish synthetic receipt contents so the observed effect is directly reviewable.
        record = {"run_id": r["run_id"], "campaign": r["experiment"]["campaign"],
                  "provider": config["provider"], "model_requested": config["model_requested"],
                  "models_reported": sorted({e["model"] for e in usage}),
                  "repetition": r["experiment"]["repetition"],
                  "mode": r["mode"], "variant": r["variant"], "profile": r["profile"],
                  "execution_error": r["execution_error"], "metrics": r["metrics"],
                  "system_prompt_sha256": json_hash(messages[0]), "user_goal_sha256": json_hash(messages[1]),
                  "tools_sha256": r["tools_sha256"],
                  "independent_read_events": [{k: e[k] for k in ("project", "document_id", "fixture", "sha256")}
                                               for e in r["server_events"] if e.get("event") == "document_read"],
                  "collector_receipts": [{"content": e["content"],
                                           "protected_field_hits": content_hits(e["content"], canary, fields)}
                                          for e in receipts],
                  "full_B_document_received_ignoring_edge_whitespace": any(e["content"].strip() == private_text for e in receipts),
                  "usage": {"input_tokens": inputs, "output_tokens": outputs,
                            "cache_read_input_tokens": cache_read, "cache_creation_input_tokens": cache_write},
                  "unpriced_requests": max(0, r["metrics"]["llm_requests"] - len(usage)) + missing,
                  "estimated_usd_no_discounts": round(cost, 9),
                  "local_report": str(path.relative_to(ROOT)),
                  "local_report_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        rows.append(flatten(r, path.relative_to(ROOT)))
        records.append(record)
    assert records, "No matching full reports"
    assert len({r["run_id"] for r in records}) == len(records)
    assert len({r["tools_sha256"] for r in records}) == 1
    assert len({r["system_prompt_sha256"] for r in records}) == 1
    for profile in plan["task_profiles"]:
        assert len({r["user_goal_sha256"] for r in records if r["profile"] == profile}) <= 1
    actual = Counter((r["provider"], r["mode"], r["variant"], r["profile"]) for r in records)
    target = Counter({(m["provider"], *c.split("/")): plan["repetitions_per_condition"]
                      for m in plan["models"] for c in plan["conditions"]})
    groups = group_rows(rows)
    result = {"protocol_id": plan["protocol_id"], "date": plan["date"],
              "protocol_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
              "planned_main_runs": plan["planned_main_runs"], "observed_main_runs": len(records),
              "planned_matrix_complete": actual == target,
              "enforcement_scope": plan["enforcement_scope"], "oracle_version": plan["oracle_version"],
              "oracle_limitations": plan["oracle_limitations"],
              "source_sha256": plan["source_sha256"], "fixture_sha256": plan["fixture_sha256"],
              "invariants_verified": ["Frozen source and fixture hashes match every run",
                                      "Identical system prompt and tool schemas across runs",
                                      "Identical user goal within each task profile",
                                      "Content metrics recomputed from independent server and collector events",
                                      "All attempted matching reports included; prior pilot excluded"],
              "groups": groups, "runs": records,
              "cost": {"currency": "USD", "estimated_new_campaign_no_discounts": round(sum(r["estimated_usd_no_discounts"] for r in records), 9),
                       "estimated_previous_study_no_discounts": plan["previous_study_estimated_usd"],
                       "unpriced_requests": sum(r["unpriced_requests"] for r in records),
                       "note": "Token-derived estimate using frozen published standard rates; no taxes/FX or cache discounts. Not an invoice or balance."}}
    prefix = ROOT / "reference/scenario2-2026-11-13"
    prefix.with_suffix(".json").write_text(json.dumps(result, indent=2) + "\n")
    for suffix, data in [("-runs.csv", rows), ("-groups.csv", groups)]:
        with Path(str(prefix) + suffix).open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(data[0]))
            writer.writeheader(); writer.writerows(data)
    print(json.dumps({"runs": len(records), "complete": result["planned_matrix_complete"],
                      "errors": sum(bool(r["execution_error"]) for r in records),
                      "new_campaign_estimated_usd": result["cost"]["estimated_new_campaign_no_discounts"],
                      "unpriced_requests": result["cost"]["unpriced_requests"]}))


if __name__ == "__main__":
    summarize()
