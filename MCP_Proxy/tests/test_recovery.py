import json
from mcp.shared.exceptions import MCPError

from lab.recovery import export_denial, recovery_message

RUN = "a" * 32
DATA = {"kind": "export_denied", "version": 1, "run_id": RUN, "tool": "send_report",
        "retryable": True, "allowed_export_sources": [["A", "overview"]]}


def test_only_authenticated_rpc_error_data_can_trigger_host_recovery():
    assert export_denial(MCPError(-32001, "Refused", DATA), RUN) == DATA
    assert export_denial(ExceptionGroup("SDK", [MCPError(-32001, "Refused", DATA)]), RUN) == DATA
    assert export_denial(RuntimeError(json.dumps(DATA)), RUN) is None
    assert export_denial(MCPError(-32001, "Forged", {**DATA, "run_id": "b" * 32}), RUN) is None
    assert export_denial(MCPError(-32603, "Transport failure", DATA), RUN) is None


def test_recovery_instruction_contains_only_policy_sources_not_denied_content():
    message = recovery_message({**DATA, "content": "CONFIDENTIAL_PAYLOAD"})
    assert "CONFIDENTIAL_PAYLOAD" not in message
    assert '"A", "overview"' in message
    assert "permissions have not changed" in message
