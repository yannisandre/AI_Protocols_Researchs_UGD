"""Explicit API adapters. No SDK agent, hosted tools, automatic retry or model fallback."""
from dataclasses import dataclass, field
import json
import os
from urllib.parse import urlsplit


class ProviderContractError(ValueError):
    """A provider response cannot be treated as a completed model decision."""


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    base_url: str
    model: str
    key: str = field(repr=False)
    max_tokens: int = 1500
    max_requests: int = 8
    anthropic_version: str = "2026-10-21"

    @classmethod
    def from_env(cls):
        provider = os.environ.get("LLM_PROVIDER", "openai")
        default = "https://api.anthropic.com/v1" if provider == "anthropic" else "https://api.openai.com/v1"
        return cls(provider=provider, base_url=os.environ.get("LLM_BASE_URL", default).rstrip("/"),
                   model=os.environ.get("LLM_MODEL", ""), key=os.environ.get("LLM_API_KEY", ""),
                   max_tokens=int(os.environ.get("LLM_MAX_COMPLETION_TOKENS", "1500")),
                   max_requests=int(os.environ.get("LLM_MAX_REQUESTS", "8")),
                   anthropic_version=os.environ.get("ANTHROPIC_VERSION", "2026-10-21"))

    def issues(self):
        problems = []
        if self.provider not in {"openai", "anthropic"}:
            problems.append("LLM_PROVIDER must be openai or anthropic")
        if not self.key or not self.model:
            problems.append("Set LLM_API_KEY and LLM_MODEL in the selected local env file")
        try:
            url = urlsplit(self.base_url)
            if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
                problems.append("LLM_BASE_URL must be HTTPS without credentials, query or fragment")
        except ValueError:
            problems.append("Invalid LLM_BASE_URL")
        if not 64 <= self.max_tokens <= 4000 or not 1 <= self.max_requests <= 16:
            problems.append("Token limit must be 64..4000; request limit must be 1..16")
        return problems

    @classmethod
    def guard_from_env(cls):
        """Separate immutable judge settings; defaults to the actor's provider/model, not its state."""
        actor = cls.from_env()
        provider = os.environ.get("GUARD_PROVIDER") or actor.provider
        same_provider = provider == actor.provider
        default_url = "https://api.anthropic.com/v1" if provider == "anthropic" else "https://api.openai.com/v1"
        return cls(provider=provider,
                   base_url=(os.environ.get("GUARD_BASE_URL") or (actor.base_url if same_provider else default_url)).rstrip("/"),
                   model=os.environ.get("GUARD_MODEL") or (actor.model if same_provider else ""),
                   key=os.environ.get("GUARD_API_KEY") or (actor.key if same_provider else ""),
                   max_tokens=int(os.environ.get("GUARD_MAX_COMPLETION_TOKENS") or "256"),
                   max_requests=int(os.environ.get("GUARD_MAX_REQUESTS") or "4"),
                   anthropic_version=os.environ.get("GUARD_ANTHROPIC_VERSION") or actor.anthropic_version)

    def public(self):
        # Never include credentials, including credentials accidentally embedded in a URL.
        try:
            url = urlsplit(self.base_url)
            authority = url.hostname or ""
            if ":" in authority:
                authority = "[" + authority + "]"
            if url.port is not None:
                authority += ":" + str(url.port)
            endpoint = f"{url.scheme}://{authority}{url.path}" if url.hostname else "invalid"
        except ValueError:
            endpoint = "invalid"
        return {"provider": self.provider, "base_url": endpoint, "model_requested": self.model,
                "max_completion_tokens": self.max_tokens, "max_requests": self.max_requests,
                "anthropic_version": self.anthropic_version if self.provider == "anthropic" else None,
                "key_present": bool(self.key), "configuration_issues": self.issues(),
                "sampling": "provider defaults; no temperature or seed sent",
                "automatic_retries": False}


def build_request(config, messages, tools):
    """Convert the common tool loop to the provider's native API schema."""
    if config.issues():
        raise ProviderContractError("Invalid provider configuration")
    if config.provider == "openai":
        wire_messages = [{k: v for k, v in m.items() if k not in {"_anthropic_content", "is_error"}}
                         for m in messages]
        return (config.base_url + "/chat/completions", {"Authorization": "Bearer " + config.key},
                {"model": config.model, "messages": wire_messages, "tools": tools, "tool_choice": "auto",
                 "parallel_tool_calls": False, "max_completion_tokens": config.max_tokens, "stream": False})
    system, wire_messages = [], []
    for message in messages:
        role = message["role"]
        if role == "system":
            system.append(message["content"])
            continue
        if role == "tool":
            block = {"type": "tool_result", "tool_use_id": message["tool_call_id"],
                     "content": message["content"], "is_error": message.get("is_error", False)}
            if wire_messages and wire_messages[-1]["role"] == "user" and all(
                    b.get("type") == "tool_result" for b in wire_messages[-1]["content"]):
                wire_messages[-1]["content"].append(block)
            else:
                wire_messages.append({"role": "user", "content": [block]})
            continue
        if role == "assistant" and "_anthropic_content" in message:
            content = message["_anthropic_content"]
        else:
            content = [{"type": "text", "text": message["content"]}] if message.get("content") else []
        wire_messages.append({"role": role, "content": content})
    native_tools = [{"name": t["function"]["name"], "description": t["function"].get("description", ""),
                     "input_schema": t["function"]["parameters"]} for t in tools]
    payload = {"model": config.model, "system": "\n".join(system), "messages": wire_messages,
               "tools": native_tools, "tool_choice": {"type": "auto", "disable_parallel_tool_use": True},
               "max_tokens": config.max_tokens, "stream": False}
    return (config.base_url + "/messages",
            {"x-api-key": config.key, "anthropic-version": config.anthropic_version}, payload)


def normalize_response(config, result):
    """Keep native Claude blocks intact for the next turn; fail on incomplete replies."""
    try:
        if not isinstance(result, dict):
            raise ProviderContractError("Provider response must be an object")
        if config.provider == "openai":
            choice = result["choices"][0]
            if choice.get("finish_reason") not in {"stop", "tool_calls"}:
                raise ProviderContractError("Incomplete/refused/unsupported OpenAI finish reason")
            message = choice["message"]
            if message.get("role") != "assistant":
                raise ProviderContractError("Expected an assistant message")
            calls = message.get("tool_calls") or []
            if bool(calls) != (choice["finish_reason"] == "tool_calls"):
                raise ProviderContractError("Tool calls disagree with finish reason")
        else:
            if result.get("stop_reason") not in {"end_turn", "tool_use", "refusal"}:
                raise ProviderContractError("Incomplete/unsupported Anthropic stop reason")
            blocks = result["content"]
            calls = [{"id": b["id"], "type": "function", "function": {
                        "name": b["name"], "arguments": json.dumps(b["input"])}}
                     for b in blocks if b["type"] == "tool_use"]
            if bool(calls) != (result["stop_reason"] == "tool_use"):
                raise ProviderContractError("Tool calls disagree with stop reason")
            message = {"role": "assistant", "content": "\n".join(b["text"] for b in blocks if b["type"] == "text"),
                       "_anthropic_content": blocks}
            if calls:
                message["tool_calls"] = calls
        ids = set()
        for call in calls:
            if call["type"] != "function" or not isinstance(call["id"], str) or not call["id"] or call["id"] in ids:
                raise ProviderContractError("Invalid or duplicate tool call id")
            ids.add(call["id"])
            if not isinstance(call["function"]["name"], str):
                raise ProviderContractError("Invalid tool name")
            arguments = json.loads(call["function"]["arguments"])
            if not isinstance(arguments, dict):
                raise ProviderContractError("Tool arguments must be a JSON object")
        return {"choices": [{"message": message}], "model": result.get("model", config.model),
                "usage": result.get("usage", {}), "provider_stop_reason":
                result.get("stop_reason") if config.provider == "anthropic" else choice["finish_reason"]}
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        if isinstance(exc, ProviderContractError):
            raise
        # Never echo the provider payload or its possibly sensitive data in an exception.
        raise ProviderContractError("Malformed provider response or tool arguments") from None
