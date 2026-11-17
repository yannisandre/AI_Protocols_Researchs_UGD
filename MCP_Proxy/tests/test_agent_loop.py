"""Offline API-contract tests with fake model replies; not LLM attack measurements."""
import asyncio
import json

import httpx
import pytest
from mcp.types import ListToolsResult, Tool, CallToolResult, TextContent

from lab import agent


def test_sdk_exception_groups_keep_actionable_root_cause():
    error = ExceptionGroup("SDK task group", [ExceptionGroup("transport", [RuntimeError("Set LLM_API_KEY")])])
    assert agent.error_message(error) == "RuntimeError: Set LLM_API_KEY"


@pytest.mark.parametrize("provider_fails", [False, True])
def test_model_tool_results_and_failed_runs_are_preserved(monkeypatch, tmp_path, provider_fails):
    monkeypatch.setattr(agent, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(agent, "secret", lambda name: "unit-test-host-token")
    monkeypatch.setattr(agent, "tls_context", lambda: None)
    called = []

    class Wire:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass

    class FakeMCP(Wire):
        protocol_version = "2026-07-28"
        def __init__(self, *args, **kwargs): pass
        async def list_tools(self):
            return ListToolsResult(tools=[Tool(name="read_document", description="Read a document", input_schema={})])
        async def call_tool(self, name, arguments):
            called.append((name, arguments))
            return CallToolResult(content=[TextContent(type="text", text="project A facts")], is_error=False)

    monkeypatch.setattr(agent.httpx2, "AsyncClient", Wire)
    monkeypatch.setattr(agent, "streamable_http_client", lambda *args, **kwargs: object())
    monkeypatch.setattr(agent, "Client", FakeMCP)

    class FakeHTTP:
        def __init__(self): self.turn = 0
        async def post(self, url, **kwargs):
            if url.endswith("/start"):
                data = {"run_id": "a"*32, "token": "fake-run-token", "goal": "Read project A"}
            elif url.endswith("/llm"):
                self.turn += 1
                if self.turn == 1:
                    message = {"content": None, "tool_calls": [{"id": "call-1", "type": "function", "function": {
                        "name": "read_document", "arguments": '{"project":"A","document_id":"overview"}'}}]}
                elif provider_fails:
                    return httpx.Response(502, json={"error": "test provider failure"})
                else:
                    messages = kwargs["json"]["messages"]
                    assert messages[-1] == {"role": "tool", "tool_call_id": "call-1", "content": "project A facts", "is_error": False}
                    message = {"content": "Done"}
                data = {"choices": [{"message": message}]}
            else:
                assert url.endswith("/finish")
                data = {"run_id": "a"*32, "metrics": {"tool_calls": len(called)}}
            return httpx.Response(200, json=data, request=httpx.Request("POST", url))

    report = asyncio.run(agent.run_once(FakeHTTP(), driver="llm", mode="enforce", variant="clean", profile="draft_a"))
    assert called == [("read_document", {"project": "A", "document_id": "overview"})]
    conversation = report["transcript"][-1]["conversation"]
    assert any(m["role"] == "tool" and m["tool_call_id"] == "call-1" for m in conversation)
    assert bool(report["execution_error"]) == provider_fails
    stored = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert stored["protocol_version"] == "2026-07-28"
    assert stored["execution_error"] == report["execution_error"]
