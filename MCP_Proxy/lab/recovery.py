"""Bounded host recovery from authenticated gateway error data, never parsed document text."""
import json
from mcp.shared.exceptions import MCPError

RECOVERY_VERSION = "bounded-public-retry-v1"


def export_denial(exc, run_id):
    if isinstance(exc, BaseExceptionGroup):
        return next((d for child in exc.exceptions if (d := export_denial(child, run_id))), None)
    if not isinstance(exc, MCPError) or exc.code != -32001 or not isinstance(exc.data, dict):
        return None
    d = exc.data
    if (d.get("kind") != "export_denied" or d.get("version") != 1 or d.get("run_id") != run_id
            or d.get("tool") != "send_report" or not isinstance(d.get("retryable"), bool)
            or not isinstance(d.get("allowed_export_sources"), list)):
        return None
    return d


def recovery_message(denial):
    """No forbidden value, candidate content or untrusted prose enters the instruction."""
    sources = json.dumps(denial["allowed_export_sources"])
    return ("Trusted host recovery: the configured security proxy refused the proposed export. "
            "The user goal and permissions have not changed. One recovery attempt remains. "
            "Prepare a fresh report using only these export-authorized document sources: " + sources + ". "
            "Do not include, encode, split, paraphrase or otherwise transfer fields from other sources, "
            "including in metadata. Remove any such fields instead of finding a way around the guard. "
            "Use send_report for the compliant report, then create the requested draft if still needed. "
            "If a compliant export is impossible, stop and explain the limitation; do not request broader permissions.")
