"""Sanitized evidence for the fixed pre-send-guard calibration; no provider calls or keys."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from lab.analyze import flatten, group_rows
from lab.provenance import json_hash

ROOT = Path(__file__).resolve().parent.parent


def price_events(events, provider, rates, requested):
    inputs = outputs = read = write = missing = 0
    for e in events:
        usage = e.get("usage", {})
        a, b = (("prompt_tokens", "completion_tokens") if provider == "openai" else ("input_tokens", "output_tokens"))
        missing += a not in usage or b not in usage
        inputs += usage.get(a, 0)
        outputs += usage.get(b, 0)
        if provider == "anthropic":
            read += usage.get("cache_read_input_tokens", 0)
            write += usage.get("cache_creation_input_tokens", 0)
    return {"input_tokens": inputs, "output_tokens": outputs, "cache_read_input_tokens": read,
            "cache_creation_input_tokens": write, "requests": requested,
            "unpriced_requests": max(0, requested - len(events)) + missing,
            "estimated_usd_no_discounts": round(((inputs + read + 2 * write) * rates["input"] + outputs * rates["output"]) / 1e6, 9)}


def summarize():
    plan_path = ROOT / "experiments/export_guards_2026-11-13.json"
    plan = json.loads(plan_path.read_text())
    specs = {m["campaign"]: m for m in plan["models"]}
    challenges = set(plan["challenge_campaigns"].values())
    rows, actor_records, challenge_records = [], [], []
    for path in sorted((ROOT / "results").glob("*.json")):
        r = json.loads(path.read_text())
        campaign = (r.get("experiment") or {}).get("campaign") if isinstance(r, dict) else None
        if campaign not in specs and campaign not in challenges:
            continue
        assert r["scenario"] == "content" and r["mode"] == "enforce"
        assert r["source_sha256"] == plan["source_sha256"]
        assert r["fixture_hashes"] == plan["fixture_sha256"]
        assert r["guard_version"] == plan["guard_version"]
        assert r["source_classification"] == plan["classification"]
        assert r["protocol_version"] == "2026-07-28"
        events, metrics = r["proxy_events"], r["metrics"]
        guards = [e for e in events if e.get("event") == "export_guard"]
        assert metrics["guard_blocked_calls"] == sum(not e["allowed"] for e in guards)
        record = {"run_id": r["run_id"], "campaign": campaign, "driver": r["driver"],
                  "guard": r["guard"], "variant": r["variant"], "profile": r["profile"],
                  "execution_error": r["execution_error"], "metrics": metrics,
                  "tools_sha256": r["tools_sha256"],
                  "guard_checks": guards,
                  "independent_reads": [{k: e[k] for k in ("project", "document_id", "fixture", "sha256")}
                                        for e in r["server_events"] if e.get("event") == "document_read"],
                  "collector_receipts": [{"content": e["content"]} for e in r["collector_events"]],
                  "local_report": str(path.relative_to(ROOT)),
                  "local_report_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        if r["guard"] == "intent":
            config = r["guard_configuration"]
            assert config["provider"] == plan["judge"]["provider"] and config["model_requested"] == plan["judge"]["model"]
            assert config["max_requests"] == plan["judge"]["max_requests_per_run"]
            assert config["max_completion_tokens"] == plan["judge"]["max_completion_tokens"]
            record["judge_usage"] = price_events([e for e in events if e.get("event") == "guard_usage"],
                                                  config["provider"], plan["judge"]["pricing_usd_per_million_tokens"], metrics["guard_requests"])
        else:
            record["judge_usage"] = {"requests": 0, "unpriced_requests": 0, "estimated_usd_no_discounts": 0}
        if campaign in specs:
            spec = specs[campaign]
            config = r["llm_configuration"]
            assert r["driver"] == "llm" and config["model_requested"] == spec["model"] and config["provider"] == spec["provider"]
            assert config["max_requests"] == plan["actor_max_requests"] and config["max_completion_tokens"] == plan["actor_output_tokens"]
            conversation = next(t["conversation"] for t in r["transcript"] if "conversation" in t)
            record.update(provider=config["provider"], model_requested=config["model_requested"],
                          actor_usage=price_events([e for e in events if e.get("event") == "llm_usage"],
                                                   config["provider"], spec["pricing_usd_per_million_tokens"], metrics["llm_requests"]),
                          system_prompt_sha256=json_hash(conversation[0]), user_goal_sha256=json_hash(conversation[1]))
            actor_records.append(record)
        else:
            assert r["driver"] == "scripted" and "challenge" in r
            challenge = r["challenge"]
            definition = next(c for c in plan["challenges"] if c["id"] == challenge["id"])
            assert challenge["expected_allow"] == definition["expected_allow"] and r["profile"] == definition["profile"]
            candidate = next(t["arguments"]["content"] for t in r["transcript"] if t.get("tool") == "send_report")
            received = any(e["content"] == candidate for e in r["collector_events"])
            assert received == challenge["candidate_received"]
            assert challenge["forbidden_candidate_received"] == (received and not definition["expected_allow"])
            record["challenge"] = challenge
            challenge_records.append(record)
        rows.append(flatten(r, path.relative_to(ROOT)))
    assert actor_records or challenge_records, "No matching full reports"
    assert len({r["run_id"] for r in actor_records + challenge_records}) == len(rows)
    if actor_records:
        assert len({r["system_prompt_sha256"] for r in actor_records}) == 1
        for profile in ["public_summary", "authorized_export"]:
            assert len({r["user_goal_sha256"] for r in actor_records if r["profile"] == profile}) <= 1
    target_actor = Counter({(m["provider"], g, *c.split("/")): plan["actor_repeats"]
                            for m in plan["models"] for g in plan["guard_arms"] for c in plan["actor_conditions"]})
    observed_actor = Counter((r["provider"], r["guard"], r["variant"], r["profile"]) for r in actor_records)
    target_challenge = Counter({(g, c["id"]): 1 for g in plan["guard_arms"] for c in plan["challenges"]})
    observed_challenge = Counter((r["guard"], r["challenge"]["id"]) for r in challenge_records)
    actor_cost = sum(r["actor_usage"]["estimated_usd_no_discounts"] for r in actor_records)
    judge_cost = sum(r["judge_usage"]["estimated_usd_no_discounts"] for r in actor_records + challenge_records)
    result = {"protocol_id": plan["protocol_id"], "protocol_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
              "source_sha256": plan["source_sha256"], "fixture_sha256": plan["fixture_sha256"],
              "actor_matrix_complete": observed_actor == target_actor,
              "challenge_matrix_complete": observed_challenge == target_challenge,
              "actor_runs": actor_records, "challenge_runs": challenge_records,
              "groups": group_rows(rows),
              "invariants_verified": ["Frozen code/fixtures and judge settings match", "All matching attempts retained",
                                      "Actor system prompt and per-profile user goal identical across guards",
                                      "Guard denial counts checked against audit events",
                                      "Constructed challenge transfers checked against exact independent receipts"],
              "cost": {"currency": "USD", "actor_estimate": round(actor_cost, 9), "judge_estimate": round(judge_cost, 9),
                       "new_total_estimate": round(actor_cost + judge_cost, 9),
                       "previous_study_estimate": plan["previous_study_estimated_usd"],
                       "unpriced_requests": sum(r["actor_usage"]["unpriced_requests"] for r in actor_records)
                       + sum(r["judge_usage"]["unpriced_requests"] for r in actor_records + challenge_records),
                       "note": "Standard token-rate estimate, not an invoice; no tax/FX, no cache discounts."}}
    prefix = ROOT / "reference/export-guards-2026-11-13"
    prefix.with_suffix(".json").write_text(json.dumps(result, indent=2) + "\n")
    for suffix, data in [("-runs.csv", rows), ("-groups.csv", result["groups"])]:
        with Path(str(prefix) + suffix).open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(data[0])); writer.writeheader(); writer.writerows(data)
    print(json.dumps({"actor_runs": len(actor_records), "challenge_runs": len(challenge_records),
                      "actor_matrix_complete": result["actor_matrix_complete"], "challenge_matrix_complete": result["challenge_matrix_complete"],
                      "errors": sum(bool(r["execution_error"]) for r in actor_records + challenge_records), "cost": result["cost"]}))


if __name__ == "__main__":
    summarize()
