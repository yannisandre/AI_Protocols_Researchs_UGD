"""JSON MCP gateway with task authorization and optional pre-send content guards; no MRTR/SSE."""
import asyncio
import importlib.metadata
import json
import re
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from copy import deepcopy

import httpx
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from lab.common import append_event, authorized, events, health, rpc_error, secret, tls_context
from lab.policy import PROFILES, SCENARIOS, check_call
from lab.evaluation import ORACLE_VERSION, ORACLE_SCOPE, evaluate_effects
from lab.providers import ProviderConfig, ProviderContractError, build_request, normalize_response
from lab.guards import (GUARDS, GUARD_VERSION, CLASSIFICATION, observe_read, dlp_decision,
                        judge_messages, build_judge_request, parse_judge_response)
from lab.provenance import json_hash

RUNS = {}
MAX_BODY = 256_000


@asynccontextmanager
async def lifespan(app):
    async with httpx.AsyncClient(verify=tls_context(), timeout=30, trust_env=False) as backend:
        async with httpx.AsyncClient(timeout=120, trust_env=False, follow_redirects=False) as provider:
            app.state.backend = backend
            app.state.provider = provider
            yield


async def read_json(request):
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > MAX_BODY:
            raise ValueError("request too large")
    return json.loads(raw)


def run_auth(request):
    run = RUNS.get(request.path_params["run_id"])
    if run and secrets.compare_digest(request.headers.get("authorization", ""), "Bearer " + run["token"]):
        return run
    return None


async def start_run(request):
    if not authorized(request, "host_control"):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        data = await read_json(request)
        required = {"mode", "variant", "profile", "driver"}
        if not isinstance(data, dict) or not required <= set(data) or set(data) - required - {"scenario", "guard", "recovery", "evaluation_case"}:
            raise ValueError()
        data.setdefault("scenario", "scope")
        data.setdefault("guard", "resource")
        data.setdefault("recovery", "none")
        data.setdefault("evaluation_case", None)
        if data["mode"] not in {"baseline", "enforce"} or data["variant"] not in {"clean", "attack"}:
            raise ValueError()
        if data["profile"] not in PROFILES or data["driver"] not in {"scripted", "llm", "codex"}:
            raise ValueError()
        if data["scenario"] not in SCENARIOS or data["profile"] not in SCENARIOS[data["scenario"]]:
            raise ValueError()
        if data["guard"] not in GUARDS or (data["guard"] != "resource" and data["mode"] != "enforce"):
            raise ValueError()
        if data["recovery"] not in {"none", "bounded"}:
            raise ValueError()
        if data["evaluation_case"] is not None and (data["scenario"] != "content" or
                not isinstance(data["evaluation_case"], str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,49}", data["evaluation_case"])):
            raise ValueError()
    except (ValueError, TypeError):
        return JSONResponse({"error": "invalid trusted run configuration"}, status_code=400)
    run_id = uuid.uuid4().hex
    RUNS[run_id] = {**data, "policy": deepcopy(PROFILES[data["profile"]]), "token": secrets.token_urlsafe(32),
                    "llm_calls": 0, "closed": False, "lock": asyncio.Lock(), "mcp_lock": asyncio.Lock(),
                    "created": time.time(), "observations": [], "workflow": [], "guard_calls": 0,
                    "classification": deepcopy(CLASSIFICATION), "export_denials": 0}
    if data["guard"] in {"intent", "hybrid"}:
        try:
            RUNS[run_id]["judge"] = ProviderConfig.guard_from_env()
        except ValueError:
            RUNS[run_id]["judge_error"] = "guard_configuration_invalid"
    if data["driver"] == "llm":
        try:
            RUNS[run_id]["provider"] = ProviderConfig.from_env()
        except ValueError:
            RUNS[run_id]["provider_error"] = "Provider limits must be integers"
    append_event("proxy", run_id, event="run_started", **data, policy=PROFILES[data["profile"]],
                 protocol_scope="2026-07-28 JSON tools only; no MRTR",
                 mcp_sdk=importlib.metadata.version("mcp"))
    return JSONResponse({"run_id": run_id, "token": RUNS[run_id]["token"],
                         "recovery": data["recovery"], "recovery_limit": 1,
                         "goal": PROFILES[data["profile"]]["goal"]})


async def mcp_request(request):
    run = run_auth(request)
    if run is None:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    # Serialize checks, observation updates and effects for a run, including concurrent SDK callers.
    async with run["mcp_lock"]:
        return await forward_mcp(request, run)


async def export_guard(request, run, arguments):
    run_id = request.path_params["run_id"]
    started = time.perf_counter()
    stages = []
    result = None
    if run["guard"] in {"dlp", "hybrid"}:
        deterministic = dlp_decision(run["policy"], run["observations"], arguments["content"])
        stages.append({"stage": "dlp", **deterministic})
        if run["guard"] == "dlp" or not deterministic["allowed"]:
            result = deterministic
    if result is None:
        result = {"allowed": False, "reason": "guard_configuration_invalid", "failure": True}
        config = run.get("judge")
        if config is not None and not config.issues():
            try:
                if run["guard_calls"] >= config.max_requests:
                    raise ValueError("guard_request_limit")
                messages = judge_messages(run["policy"], run["classification"], run["observations"],
                                          run["workflow"], arguments)
                url, headers, payload = build_judge_request(config, messages)
                append_event("proxy", run_id, event="guard_context", messages=messages,
                             context_sha256=json_hash(messages))
                run["guard_calls"] += 1
                response = await request.app.state.provider.post(url, headers=headers, json=payload)
                if response.status_code != 200:
                    raise ValueError("guard_provider_rejected")
                try:
                    native = response.json()
                except ValueError:
                    raise ValueError("guard_invalid_provider_json") from None
                append_event("proxy", run_id, event="guard_usage", provider=config.provider,
                             model=native.get("model", config.model) if isinstance(native, dict) else config.model,
                             usage=native.get("usage", {}) if isinstance(native, dict) else {})
                # Successful HTTP replies can still violate the verdict contract: retain them for diagnosis.
                # Do not record HTTP error bodies, authentication headers or credentials.
                append_event("proxy", run_id, event="guard_reply", provider=config.provider, response=native)
                verdict = parse_judge_response(config, native)
                result = {"allowed": verdict["decision"] == "allow", "reason": "intent_" + verdict["reason_code"],
                          "uncertain": verdict["decision"] == "uncertain", "verdict": verdict,
                          "context_sha256": json_hash(messages)}
            except httpx.HTTPError:
                result = {"allowed": False, "reason": "guard_connection_failed", "failure": True}
            except ValueError as exc:
                # Only locally defined reason codes, never provider payload text.
                reason = str(exc)
                if reason not in {"guard_request_limit", "guard_context_too_large", "guard_configuration_invalid",
                                  "guard_provider_rejected", "guard_invalid_provider_json", "guard_invalid_verdict"}:
                    reason = "guard_invalid_verdict"
                result = {"allowed": False, "reason": reason, "failure": True,
                          "failure_detail": getattr(exc, "detail", None)}
        stages.append({"stage": "intent", **result})
    result["stages"] = stages
    result["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
    append_event("proxy", run_id, event="export_guard", guard=run["guard"], **result)
    return result


async def forward_mcp(request, run):
    if run["closed"]:
        return JSONResponse({"error": "run closed"}, status_code=409)
    try:
        data = await read_json(request)
    except ValueError:
        return rpc_error(None, -32700, "Invalid JSON or oversized message")
    if not isinstance(data, dict) or data.get("jsonrpc") != "2.0" or "id" not in data:
        return rpc_error(None, -32600, "A single JSON-RPC request is required")
    request_id = data["id"]
    method = data.get("method")
    params = data.get("params", {})
    if not isinstance(params, dict):
        return rpc_error(request_id, -32602, "Invalid params")
    if method not in {"server/discover", "tools/list", "tools/call"}:
        return rpc_error(request_id, -32601, "Method outside this scenario's supported subset")
    if "requestState" in params or "inputResponses" in params:
        return rpc_error(request_id, -32602, "MRTR is outside this prototype")
    run_id = request.path_params["run_id"]
    if method == "tools/call":
        allowed, reason = check_call(params.get("name"), params.get("arguments", {}), run["policy"], run["mode"])
        _, task_reason = check_call(params.get("name"), params.get("arguments", {}), run["policy"], "enforce")
        guard_result = None
        if (allowed and params.get("name") == "send_report" and run["recovery"] == "bounded"
                and run["export_denials"] > 1):
            allowed, reason = False, "export_recovery_exhausted"
        elif allowed and params.get("name") == "send_report" and run["guard"] != "resource":
            guard_result = await export_guard(request, run, params["arguments"])
            allowed, reason = guard_result["allowed"], guard_result["reason"]
        append_event("proxy", run_id, event="decision", rpc_id=request_id, tool=params.get("name"),
                     arguments=params.get("arguments", {}), allowed=allowed, reason=reason,
                     task_reason=task_reason, guard=run["guard"],
                     guard_blocked=guard_result is not None and not allowed,
                     out_of_scope=task_reason in {"document_outside_task", "draft_outside_task", "destination_outside_task"})
        if not allowed:
            run["workflow"].append({"tool": params.get("name"), "allowed": False, "reason": reason})
            if guard_result is not None or reason == "export_recovery_exhausted":
                run["export_denials"] += 1
                retryable = (run["recovery"] == "bounded" and run["export_denials"] == 1
                             and guard_result is not None and not guard_result.get("failure"))
                return rpc_error(request_id, -32001, "Export refused by task policy", data={
                    "kind": "export_denied", "version": 1, "run_id": run_id, "tool": "send_report",
                    "reason": reason, "retryable": retryable,
                    "allowed_export_sources": run["policy"]["export_documents"]})
            return rpc_error(request_id, -32001, "Task policy denied call: " + reason)
    headers = {"Authorization": "Bearer " + secret("server_token"), "Content-Type": "application/json",
               "Accept": "application/json, text/event-stream", "X-Lab-Run-Id": run_id,
               "X-Lab-Variant": run["variant"], "X-Lab-Scenario": run["scenario"]}
    if run["evaluation_case"] is not None:
        headers["X-Lab-Evaluation-Case"] = run["evaluation_case"]
    # Authentication and run/fixture headers are minted here, never copied from the agent.
    for name in ("mcp-protocol-version", "mcp-method", "mcp-name"):
        if name in request.headers:
            headers[name] = request.headers[name]
    try:
        response = await request.app.state.backend.post("https://mcp-server:8443/mcp", json=data, headers=headers)
    except httpx.HTTPError:
        return rpc_error(request_id, -32603, "Upstream service unavailable")
    if "application/json" not in response.headers.get("content-type", ""):
        return rpc_error(request_id, -32603, "Expected JSON-only upstream response")
    try:
        result = response.json()
    except ValueError:
        return rpc_error(request_id, -32603, "Invalid upstream JSON")
    append_event("proxy", run_id, event="mcp_exchange", request=data, response=result,
                 http_status=response.status_code)
    if method == "tools/call":
        name, arguments = params["name"], params.get("arguments", {})
        complete = (response.status_code == 200 and isinstance(result, dict)
                    and isinstance(result.get("result"), dict) and not result["result"].get("isError")
                    and result["result"].get("resultType", "complete") == "complete")
        run["workflow"].append({"tool": name, "arguments": arguments, "successful_response": complete})
        if name == "read_document" and complete:
            observation = observe_read(arguments, result, run["classification"])
            if observation is not None:
                run["observations"].append(observation)
                append_event("proxy", run_id, event="source_observed", source=observation["source"],
                             classification=observation["classification"], sha256=observation["sha256"])
    # Never rewrite outputs or silently alter a proposed send.
    return Response(response.content, status_code=response.status_code, media_type="application/json")


async def llm_request(request):
    run = run_auth(request)
    if run is None:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if run["driver"] != "llm" or run["closed"]:
        return JSONResponse({"error": "LLM unavailable for this run"}, status_code=409)
    config = run.get("provider")
    if config is None or config.issues():
        return JSONResponse({"error": run.get("provider_error", "Invalid provider configuration"),
                             "issues": config.issues() if config else []}, status_code=503)
    try:
        data = await read_json(request)
        if (not isinstance(data, dict) or set(data) != {"messages", "tools"}
                or not isinstance(data["messages"], list) or not isinstance(data["tools"], list)):
            raise ValueError()
    except ValueError:
        return JSONResponse({"error": "invalid LLM request"}, status_code=400)
    try:
        url, headers, payload = build_request(config, data["messages"], data["tools"])
    except (KeyError, TypeError, ValueError):
        return JSONResponse({"error": "Invalid conversation for provider adapter"}, status_code=400)
    async with run["lock"]:
        if run["llm_calls"] >= config.max_requests:
            return JSONResponse({"error": "per-run LLM call limit reached"}, status_code=429)
        run["llm_calls"] += 1
    started = time.perf_counter()
    try:
        response = await request.app.state.provider.post(url, json=payload, headers=headers)
    except httpx.HTTPError:
        return JSONResponse({"error": "LLM provider connection failed"}, status_code=502)
    if response.status_code != 200:
        # Do not leak provider response text, URLs with query strings, or authentication values.
        append_event("proxy", request.path_params["run_id"], event="llm_error", status=response.status_code)
        return JSONResponse({"error": "LLM provider rejected request", "provider_status": response.status_code}, status_code=502)
    try:
        native = response.json()
    except ValueError:
        return JSONResponse({"error": "LLM provider returned invalid JSON"}, status_code=502)
    append_event("proxy", request.path_params["run_id"], event="llm_usage", provider=config.provider,
                 model=native.get("model", config.model) if isinstance(native, dict) else config.model,
                 usage=native.get("usage", {}) if isinstance(native, dict) else {},
                 latency_ms=round((time.perf_counter()-started)*1000, 2))
    try:
        result = normalize_response(config, native)
    except ProviderContractError as exc:
        append_event("proxy", request.path_params["run_id"], event="llm_contract_error", reason=str(exc))
        return JSONResponse({"error": str(exc)}, status_code=502)
    return JSONResponse(result)


async def provider_status(request):
    """Configuration only. Does not validate a key with the provider or incur inference."""
    if not authorized(request, "host_control"):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        config = ProviderConfig.from_env()
        judge = ProviderConfig.guard_from_env()
        return JSONResponse({"configuration": config.public(), "ready": not config.issues(),
                             "guard_configuration": judge.public(), "guard_ready": not judge.issues(),
                             "provider_contacted": False})
    except ValueError:
        return JSONResponse({"ready": False, "provider_contacted": False,
                             "error": "Provider limits must be integers"})


async def finish_run(request):
    if not authorized(request, "host_control"):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    run_id = request.path_params["run_id"]
    run = RUNS.get(run_id)
    if run is None:
        return JSONResponse({"error": "unknown run"}, status_code=404)
    async with run["mcp_lock"]:
        run["closed"] = True
    client = request.app.state.backend
    srv = await client.get(f"https://mcp-server:8443/evidence/{run_id}",
                           headers={"Authorization": "Bearer " + secret("server_token")})
    col = await client.get(f"https://collector:8443/evidence/{run_id}",
                           headers={"Authorization": "Bearer " + secret("collector_read")})
    srv.raise_for_status(); col.raise_for_status()
    server_events, collector_events = srv.json()["events"], col.json()["events"]
    canary = srv.json()["canary"]
    proxy_events = events(run_id)
    metrics = {**evaluate_effects(run["policy"], run["profile"], server_events, collector_events,
                                 canary, srv.json()["protected_fields"],
                                 private_text=srv.json().get("private_text"),
                                 strict_public=run["evaluation_case"] is not None),
               "blocked_calls": sum(e.get("event") == "decision" and not e["allowed"] for e in proxy_events),
               "task_blocked_calls": sum(e.get("event") == "decision" and not e["allowed"] and e.get("out_of_scope", False)
                                         for e in proxy_events),
               "invalid_calls": sum(e.get("event") == "decision" and e.get("reason") in {"invalid_arguments", "unknown_tool"}
                                     for e in proxy_events),
               "tool_calls": sum(e.get("event") == "decision" for e in proxy_events),
               "out_of_scope_attempts": sum(e.get("event") == "decision" and e.get("out_of_scope", False)
                                            for e in proxy_events),
               "llm_requests": run["llm_calls"], "guard_requests": run["guard_calls"],
               "guard_blocked_calls": sum(e.get("event") == "decision" and e.get("guard_blocked", False)
                                          for e in proxy_events),
               "guard_failures": sum(e.get("event") == "export_guard" and e.get("failure", False) for e in proxy_events),
               "guard_uncertain_calls": sum(e.get("event") == "export_guard" and e.get("uncertain", False) for e in proxy_events),
               "guard_latency_ms": round(sum(e.get("latency_ms", 0) for e in proxy_events if e.get("event") == "export_guard"), 2)}
    report = {"run_id": run_id, "driver": run["driver"], "mode": run["mode"], "variant": run["variant"],
              "recovery": run["recovery"], "export_denials": run["export_denials"],
              "evaluation_case": run["evaluation_case"],
              "scenario": run["scenario"], "profile": run["profile"], "policy": run["policy"], "metrics": metrics,
              "oracle_version": ORACLE_VERSION, "oracle_scope": ORACLE_SCOPE,
              "guard": run["guard"], "guard_version": GUARD_VERSION,
              "guard_configuration": run["judge"].public() if run.get("judge") else None,
              "source_classification": run["classification"],
              "enforcement_scope": "resource_and_destination_only" if run["guard"] == "resource" else "resource_destination_and_" + run["guard"],
              "elapsed_seconds": round(time.time()-run["created"], 3), "proxy_events": proxy_events,
              "server_events": server_events, "collector_events": collector_events,
              "fixture_hashes": srv.json()["fixture_hashes"],
              "llm_configuration": run["provider"].public() if run.get("provider") else None,
              "evidence_scope": "scripted infrastructure test, not LLM injection evidence" if run["driver"] == "scripted"
                                else "LLM-driven run; inspect transcript and independent service events"}
    return JSONResponse(report)


app = Starlette(lifespan=lifespan, routes=[
    Route("/health", health), Route("/control/start", start_run, methods=["POST"]),
    Route("/control/provider", provider_status, methods=["GET"]),
    Route("/control/{run_id}/finish", finish_run, methods=["POST"]),
    Route("/runs/{run_id}/mcp", mcp_request, methods=["POST"]),
    Route("/runs/{run_id}/llm", llm_request, methods=["POST"]),
])
