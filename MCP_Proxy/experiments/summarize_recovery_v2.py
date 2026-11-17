"""Recompute fixed v2 effects, recovery, usage and public evidence without model requests."""
import base64
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from lab.analyze import flatten, group_rows
from lab.evaluation import evaluate_effects, effect_hits
from lab.provenance import json_hash
from experiments.summarize_export_guards import price_events

ROOT = Path(__file__).resolve().parent.parent


def summarize():
    plan_path = ROOT / "experiments/recovery_v2_2026-11-13.json"
    plan = json.loads(plan_path.read_text())
    specs = {m["campaign"]: m for m in plan["models"]}
    dataset = json.loads((ROOT / "fixtures/evaluation_v2/cases.json").read_text())
    private = (ROOT / "fixtures/evaluation_v2/B_confidential.txt").read_text()
    canary = re.search(r"(?m)^Canary: ([^\r\n]+)$", private).group(1)
    fields = {"B_budget": re.search(r"budget is (.+?)\.", private).group(1), "B_budget_words": dataset["budget_words"]}
    main, prep, rows = [], [], []
    for path in sorted((ROOT / "results").glob("*.json")):
        r = json.loads(path.read_text())
        if not isinstance(r, dict): continue
        campaign = (r.get("experiment") or {}).get("campaign")
        if campaign not in specs and campaign != plan["preparation_campaign"]: continue
        is_main = campaign in specs
        spec = specs.get(campaign, plan["models"][0])
        config = r["llm_configuration"]
        assert config["provider"] == spec["provider"] and config["model_requested"] == spec["model"]
        assert config["max_requests"] == plan["actor_max_requests"] and config["max_completion_tokens"] == plan["actor_output_tokens"]
        assert r["source_sha256"] == plan["source_sha256"]
        assert r["fixture_hashes"] == plan["fixture_sha256"]
        assert r["guard_version"] == plan["guard_version"] and r["oracle_version"] == plan["oracle_version"]
        expected = evaluate_effects(r["policy"], r["profile"], r["server_events"], r["collector_events"],
                                    canary, fields, private_text=private, strict_public=True)
        assert all(r["metrics"][k] == v for k, v in expected.items()), "Effect metric mismatch"
        events, metrics = r["proxy_events"], r["metrics"]
        actor_usage = price_events([e for e in events if e.get("event") == "llm_usage"], spec["provider"],
                                  spec["pricing_usd_per_million_tokens"], metrics["llm_requests"])
        guard_usage = price_events([e for e in events if e.get("event") == "guard_usage"], plan["judge"]["provider"],
                                  plan["judge"]["pricing_usd_per_million_tokens"], metrics["guard_requests"])
        if r["guard"] == "hybrid":
            gc = r["guard_configuration"]
            assert gc["provider"] == plan["judge"]["provider"] and gc["model_requested"] == plan["judge"]["model"]
            assert gc["max_requests"] == plan["judge"]["max_requests_per_run"] and gc["max_completion_tokens"] == plan["judge"]["max_completion_tokens"]
        checks = [e for e in events if e.get("event") == "export_guard"]
        for check in checks:
            if r["guard"] == "hybrid" and not check["stages"][0]["allowed"]:
                assert len(check["stages"]) == 1 and check["stages"][0]["stage"] == "dlp"
        pending, assessed = None, []
        for event in events:
            if event.get("event") == "export_guard": pending = event
            elif event.get("event") == "decision" and event.get("tool") == "send_report":
                content = event.get("arguments", {}).get("content", "")
                hits = effect_hits(content, canary, fields)
                assessed.append({"allowed": event["allowed"], "reason": event["reason"],
                                 "oracle_private_hits": hits, "content": content,
                                 "guard_failure": bool(pending and pending.get("failure")),
                                 "guard_uncertain": bool(pending and pending.get("uncertain"))})
                pending = None
        record = {"run_id": r["run_id"], "campaign": campaign, "provider": config["provider"],
                  "model_requested": config["model_requested"], "case": r["evaluation_case"],
                  "guard": r["guard"], "recovery": r["recovery"],
                  "repetition": (r.get("experiment") or {}).get("repetition"),
                  "variant": r["variant"], "profile": r["profile"], "execution_error": r["execution_error"],
                  "metrics": metrics, "actor_usage": actor_usage, "judge_usage": guard_usage,
                  "guard_checks": checks, "assessed_send_candidates": assessed,
                  "collector_receipts": [{"content": e["content"], "oracle_private_hits": effect_hits(e["content"], canary, fields)}
                                         for e in r["collector_events"]],
                  "judge_contract_failures": [{"reason": e["reason"], "detail": e.get("failure_detail")}
                                              for e in checks if e.get("failure")],
                  "raw_judge_replies": [e["response"] for e in events if e.get("event") == "guard_reply"],
                  "independent_reads": [{k: e[k] for k in ("project", "document_id", "fixture", "sha256")}
                                        for e in r["server_events"] if e.get("event") == "document_read"],
                  "local_report": str(path.relative_to(ROOT)),
                  "local_report_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        if is_main:
            assert r["protocol_version"] == "2026-07-28" and r["recovery_version"] == plan["recovery_version"]
            conversation = next(t["conversation"] for t in r["transcript"] if "conversation" in t)
            record.update(system_prompt_sha256=json_hash(conversation[0]), user_goal_sha256=json_hash(conversation[1]),
                          tools_sha256=r["tools_sha256"])
            assert metrics["recovered_task"] == bool(metrics["recovery_notifications"] and metrics["safe_task_completion"] and not r["execution_error"])
            assert metrics["recovery_notifications"] <= 1
            main.append(record)
            rows.append(flatten(r, path.relative_to(ROOT)))
        else: prep.append(record)
    assert main or prep, "No matching reports"
    assert len({r["run_id"] for r in main + prep}) == len(main + prep)
    if main:
        assert len({r["system_prompt_sha256"] for r in main}) == 1
        assert len({r["tools_sha256"] for r in main}) == 1
        for profile in {r["profile"] for r in main}:
            assert len({r["user_goal_sha256"] for r in main if r["profile"] == profile}) == 1
    target = Counter({(m["provider"], c["id"], g, "bounded"): plan["repetitions"]
                      for m in plan["models"] for c in plan["cases"] for g in plan["guards"]})
    target.update({(m["provider"], "receipt_injection", "dlp", "none"): plan["repetitions"] for m in plan["models"]})
    observed = Counter((r["provider"], r["case"], r["guard"], r["recovery"]) for r in main)
    def cost(records):
        return round(sum(r["actor_usage"]["estimated_usd_no_discounts"] + r["judge_usage"]["estimated_usd_no_discounts"] for r in records), 9)
    result = {"protocol_id": plan["protocol_id"], "protocol_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
              "source_sha256": plan["source_sha256"], "fixture_sha256": plan["fixture_sha256"],
              "planned_runs": plan["planned_total_runs"], "observed_main_runs": len(main),
              "matrix_complete": observed == target, "groups": group_rows(rows),
              "main_runs": main, "preparation_runs_separate": prep,
              "cost": {"currency": "USD", "main_estimate": cost(main), "preparation_estimate": cost(prep),
                       "previous_study_estimate": plan["previous_study_estimated_usd"],
                       "unpriced_requests": sum(r[t]["unpriced_requests"] for r in main + prep for t in ["actor_usage", "judge_usage"]),
                       "note": "Frozen standard rates; no taxes/FX, no cache discounts. Not an invoice or hard monetary cap."},
              "invariants_verified": ["Source, fixture and judge settings match frozen plan", "Corpus fixed before implementation and unchanged",
                                      "Initial actor system prompt and per-profile user goal equal across arms",
                                      "Effects recomputed independently; complete B exports checked",
                                      "Recovery notifications bounded; successful recovery requires real effects",
                                      "Hybrid deterministic refusals short-circuit semantic classification",
                                      "Preparation attempts retained separately; no replacement of failed main cells"]}
    prefix = ROOT / "reference/recovery-v2-2026-11-13"
    prefix.with_suffix(".json").write_text(json.dumps(result, indent=2) + "\n")
    for suffix, data in [("-runs.csv", rows), ("-groups.csv", result["groups"])]:
        if not data: continue
        with Path(str(prefix) + suffix).open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(data[0])); writer.writeheader(); writer.writerows(data)
    print(json.dumps({"main_runs": len(main), "complete": result["matrix_complete"],
                      "errors": sum(bool(r["execution_error"]) for r in main),
                      "leaks": sum(r["metrics"]["unauthorized_disclosure"] for r in main),
                      "recovered_tasks": sum(r["metrics"]["recovered_task"] for r in main), "cost": result["cost"]}))


if __name__ == "__main__": summarize()
