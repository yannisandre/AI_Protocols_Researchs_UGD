"""Prospectively fixed dataset/guard matrix; independent runs, no replacements after errors."""
import argparse
import asyncio
import json
import random
from datetime import datetime, timezone

import httpx

from lab.agent import run_once, network_checks, RESULTS_DIR
from lab.common import tls_context

CASES = [
    ("public_plain", "clean", "public_summary"),
    ("public_receipt", "clean", "public_summary"),
    ("receipt_injection", "attack", "public_summary"),
    ("reviewer_injection", "attack", "public_summary"),
    ("authorized_export", "clean", "authorized_export"),
]


async def main(args):
    reports = []
    rng = random.Random(args.order_seed)
    async with httpx.AsyncClient(verify=tls_context(), timeout=130, trust_env=False) as http:
        checks = await network_checks(http)
        stop = False
        for repetition in range(1, args.repeats + 1):
            cells = [(case, variant, profile, guard, "bounded") for case, variant, profile in CASES
                     for guard in ("resource", "dlp", "hybrid")]
            cells.append(("receipt_injection", "attack", "public_summary", "dlp", "none"))
            rng.shuffle(cells)
            for case, variant, profile, guard, recovery in cells:
                report = await run_once(http, driver="llm", mode="enforce", scenario="content",
                                        variant=variant, profile=profile, guard=guard, recovery=recovery,
                                        evaluation_case=case, experiment={"campaign": args.campaign,
                                        "repetition": repetition, "suite_order_seed": args.order_seed,
                                        "evaluation_id": "prospective-evaluation-v2"})
                reports.append(report)
                failure_reasons = {e["reason"] for e in report["proxy_events"]
                                   if e.get("event") == "export_guard" and e.get("failure")}
                # Schema/decision-contract failures retire this run and remain in the fixed matrix.
                # Authentication, transport, budget and actor API errors stop the provider campaign.
                if report["execution_error"] and not (
                        report["execution_error"] == "Guard infrastructure failure; inspect export_guard events"
                        and failure_reasons == {"guard_invalid_verdict"}):
                    stop = True
                    break
            if stop:
                break
    summary = {"campaign": args.campaign, "network_checks": checks, "repeats": args.repeats,
               "planned_runs": (len(CASES) * 3 + 1) * args.repeats, "observed_runs": len(reports),
               "runs": [{k: r[k] for k in ("run_id", "evaluation_case", "guard", "recovery", "metrics", "execution_error")}
                        for r in reports]}
    path = RESULTS_DIR / ("evaluation_v2_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
    path.write_text(json.dumps(summary, indent=2) + "\n")
    print("Evaluation summary: " + str(path), flush=True)
    if len(reports) != summary["planned_runs"]:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--repeats", type=int, choices=range(1, 4), default=3)
    parser.add_argument("--order-seed", type=int, default=20261116)
    asyncio.run(main(parser.parse_args()))
