import hmac
import json
import os
import re
import ssl
from datetime import datetime, timezone
from pathlib import Path

from starlette.responses import JSONResponse


def secret(name):
    return Path(os.environ.get("SECRETS_DIR", "/secrets"), name).read_text().strip()


def authorized(request, name):
    return hmac.compare_digest(request.headers.get("authorization", ""), "Bearer " + secret(name))


def tls_context():
    return ssl.create_default_context(cafile=os.environ.get("LAB_CA", "/certs/ca.pem"))


def valid_run(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{32}", value):
        raise ValueError("Invalid run identifier")
    return value


def append_event(component, run_id, **fields):
    run_id = valid_run(run_id)
    event = {"timestamp": datetime.now(timezone.utc).isoformat(), "component": component,
             "run_id": run_id, **fields}
    root = Path(os.environ.get("DATA_DIR", "/data"))
    root.mkdir(parents=True, exist_ok=True)
    # Each service has one worker; synchronous append prevents asyncio interleaving.
    with (root / (run_id + ".jsonl")).open("a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def events(run_id):
    path = Path(os.environ.get("DATA_DIR", "/data"), valid_run(run_id) + ".jsonl")
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


async def health(request):
    return JSONResponse({"status": "ok"})


def rpc_error(request_id, code, message, data=None):
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return JSONResponse({"jsonrpc": "2.0", "id": request_id,
                         "error": error})
