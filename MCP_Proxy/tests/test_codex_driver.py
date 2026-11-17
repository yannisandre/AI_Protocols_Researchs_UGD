"""Control-plane and credential handling checks without a real Codex login/model."""
import asyncio
import base64
import json
import time
from types import SimpleNamespace

import pytest

from lab import codex_agent as codex


def fake_auth(tmp_path, monkeypatch, expires):
    source = tmp_path / "source.json"
    payload = base64.urlsafe_b64encode(json.dumps({"exp": expires}).encode()).decode().rstrip("=")
    source.write_text(json.dumps({"tokens": {"access_token": "unit-test." + payload + ".signature"}}))
    home = tmp_path / "isolated-home"
    monkeypatch.setenv("CODEX_SOURCE_AUTH", str(source))
    monkeypatch.setenv("CODEX_HOME", str(home))
    return source, home


def test_credentials_are_linked_not_copied_or_modified(tmp_path, monkeypatch):
    source, home = fake_auth(tmp_path, monkeypatch, time.time() + 3600)
    before = source.read_bytes()
    monkeypatch.setattr(codex.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout="Logged in using ChatGPT", stderr=""))
    codex.prepare_auth(180)
    assert (home / "auth.json").is_symlink()
    assert (home / "auth.json").resolve() == source.resolve()
    assert source.read_bytes() == before


def test_expiring_session_fails_before_refresh_or_model_use(tmp_path, monkeypatch):
    fake_auth(tmp_path, monkeypatch, time.time() + 60)
    def forbidden(*args, **kwargs):
        raise AssertionError("An expiring credential must not start Codex")
    monkeypatch.setattr(codex.subprocess, "run", forbidden)
    with pytest.raises(RuntimeError, match="refreshing on the host"):
        codex.prepare_auth(180)


def test_api_key_login_is_not_used_for_subscription_experiment(tmp_path, monkeypatch):
    fake_auth(tmp_path, monkeypatch, time.time() + 3600)
    monkeypatch.setattr(codex.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout="Logged in using an API key", stderr=""))
    with pytest.raises(RuntimeError, match="not an API key"):
        codex.prepare_auth(180)


def test_run_token_is_not_in_command_configuration_or_trace(tmp_path):
    run = {"run_id": "a"*32, "token": "DO_NOT_LOG_THIS"}
    session = codex.CodexSession(run, tmp_path)
    config = codex.config_for(run)
    assert run["token"] not in json.dumps(config)
    assert session.clean({"nested": {"token": run["token"]}})["nested"]["token"] == "[REDACTED_RUN_TOKEN]"
    assert config["mcp_servers"]["lab"]["enabled_tools"] == ["create_draft", "read_document", "send_report"]
    assert config["sandbox_mode"] == "read-only"


@pytest.mark.parametrize("kind", ["commandExecution", "fileChange", "webSearch", "dynamicToolCall"])
def test_unexpected_tool_activity_invalidates_a_run(tmp_path, kind):
    async def scenario():
        session = codex.CodexSession({"run_id": "a"*32, "token": "test-only"}, tmp_path)
        stream = asyncio.StreamReader()
        stream.feed_data((json.dumps({"method": "item/started", "params": {"item": {"type": kind}}}) + "\n").encode())
        stream.feed_eof()
        session.process = SimpleNamespace(stdout=stream)
        await session.read_stdout()
        assert kind in session.violation
    asyncio.run(scenario())


def test_turn_really_starts_a_generation_and_waits_for_completion(tmp_path):
    async def scenario():
        session = codex.CodexSession({"run_id": "a"*32, "token": "test-only"}, tmp_path)
        calls = []
        async def call(method, params):
            calls.append((method, params))
            await session.messages.put({"method": "turn/completed", "params": {"turn": {"status": "completed"}}})
        session.call = call
        await session.turn("thread-test", "Create a project A draft", 1)
        assert calls[0][0] == "turn/start"
        assert calls[0][1]["input"][0]["text"] == "Create a project A draft"
        assert not any(method == "mcpServer/tool/call" for method, _ in calls)
    asyncio.run(scenario())
